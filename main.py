'''
LifeOS v2 - Async Fast Track + Sensory Cortex Integration
'''
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, Request, Response
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import TelegramError

from src.config import load_credentials
from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager
from src.identity_manager import IdentityManager, UserRole
from src.utils.tool_context import inject_runtime_context
from src.logging_config import configure_logging
from src.social.shield import SocialShield

# --- SENSORY IMPORTS ---
from src.sensory import SensoryCortex
from src.sensory.drivers.visual_driver import VisualDriver
from src.sensory.drivers.audio_driver import AudioDriver

configure_logging()
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_TOKEN = load_credentials()
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
RUN_MODE = os.getenv('RUN_MODE', 'polling').lower()
PORT = int(os.getenv('PORT', '8080'))
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')

session_manager = SessionManager()
orchestrator = CrewOrchestrator(session_manager=session_manager)

# --- Lógica del Bot ---
async def send_smart_response(update: Update, text: str) -> Message | None:
    """
    Trocea mensajes > 4096 caracteres para evitar el crash de Telegram.
    Devuelve el último mensaje enviado para fines de logging.
    """
    MAX_LENGTH = 4000 # Margen de seguridad
    
    if not text: return None
    if not isinstance(text, str): text = str(text)

    last_msg = None

    # Caso 1: Mensaje corto (envío directo)
    if len(text) <= MAX_LENGTH:
        try:
            last_msg = await update.message.reply_text(text, parse_mode='Markdown')
        except TelegramError:
            last_msg = await update.message.reply_text(text)
        return last_msg

    # Caso 2: Mensaje largo (Chunking)
    chunks = []
    while text:
        if len(text) <= MAX_LENGTH:
            chunks.append(text)
            break
        
        split_index = text.rfind('\n', 0, MAX_LENGTH)
        if split_index == -1: 
            split_index = MAX_LENGTH
            
        chunks.append(text[:split_index])
        text = text[split_index:].lstrip()

    for chunk in chunks:
        try:
            last_msg = await update.message.reply_text(chunk, parse_mode='Markdown')
        except TelegramError:
            last_msg = await update.message.reply_text(chunk)
    
    return last_msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔥 LifeOS v2 Online.\nModo: {RUN_MODE.upper()}")

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user: return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # 1. SENSORY CORTEX PROCESSING (run before Social Shield to ensure payload/logging is set)
    sensory_payload = await SensoryCortex().process(update)

    # 0. SOCIAL SHIELD CHECK
    engage, sanitized_input = await SocialShield.should_engage(update, context)
    if not engage:
        logging.info(f"🛡️ Shield: Bot remains silent in chat {chat_id}")
        # Passive Context Ingestion: if this was a non-trigger message in a group, persist it (Firestore write only)
        chat_type = update.effective_chat.type
        if chat_type in ['group', 'supergroup']:
            try:
                log_content, input_type = SessionManager.build_log_content(sensory_payload, sanitized_input, update.message)
                name = getattr(update.effective_user, 'first_name', None) or getattr(update.effective_user, 'username', 'Unknown')
                await SessionManager.add_message(
                    chat_id,
                    {
                        "role": "user",
                        "content": log_content,
                        "user_id": user_id,
                        "name": name,
                        "message_id": getattr(update.message, 'message_id', ''),
                        "input_type": input_type
                    }
                )
                logging.info(f"💾 Passive ingestion: saved non-trigger message for chat {chat_id}")
            except Exception as e:
                logging.warning(f"⚠️ Passive ingestion failed for chat {chat_id}: {e}")
        return

    # 1. Identidad
    current_user = await IdentityManager.get_user(user_id)
    
    # --- 🚧 PROTOCOLO DE INTERCEPCIÓN 🚧 ---
    if current_user.role == UserRole.BLOCKED:
        logging.info(f"🚫 Usuario bloqueado {user_id} intentó contactar.")
        return 

    if current_user.role == UserRole.PENDING:
        username = update.effective_user.username or "NoUsername"
        first_name = update.effective_user.first_name or "Unknown"
        
        logging.warning(f"🚨 INTRUSIÓN DETECTADA: {first_name} (@{username}) - ID: {user_id}")
        current_user.name = first_name
        current_user.description = f"@{username}" 
        
        await IdentityManager.register_user(current_user)
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text="🛡️ **Protocolo de Seguridad Activo**\n\nAcceso restringido pendiente de aprobación del Administrador.",
            parse_mode='Markdown'
        )
        
        if ADMIN_USER_ID:
            alert_text = (
                f"🚨 **ALERTA DE INTRUSIÓN**\n\n"
                f"**Nombre:** {first_name}\n"
                f"**Handle:** @{username}\n"
                f"**ID:** `{user_id}`\n\n"
                f"Para autorizar, responde:\n"
                f"`Autoriza {user_id} como FAMILY, nombre: {first_name}, desc: Pareja`"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=alert_text, parse_mode='Markdown')
            except Exception as e:
                logging.error(f"❌ Error al avisar al ADMIN: {e}")
        
        return 
    # --- FIN PROTOCOLO INICIAL ---

    logging.info("👤 Usuario: %s (%s)", current_user.name, current_user.role)
    inject_runtime_context(current_user)
    #await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    user_input: str | list[dict[str, Any]] | None = None
    is_multimodal = False
    input_type = "text" # Default to text

    if sensory_payload:
        user_input = sensory_payload["content"]
        is_multimodal = True
        input_type = sensory_payload.get("metadata", {}).get("input_type", "multimodal")
    elif update.message and update.message.text:
        # Use sanitized text (handles removed) if Shield provided one for mention-activations
        user_input = sanitized_input if sanitized_input is not None else update.message.text
        if sanitized_input is not None and isinstance(user_input, str) and user_input != (update.message.text or ""):
            logging.info(f"🔎 Sanitized input for routing: '{user_input}' (bot handle removed)")
    else:
        return

    # 3. ENRUTAMIENTO Y EJECUCIÓN
    try:
        target_agent = None
        bypass_context = None

        if update.message and update.message.reply_to_message:
            parent_id = update.message.reply_to_message.message_id
            parent_meta = await SessionManager.get_message_metadata(chat_id, parent_id)
            if parent_meta and parent_meta.get('agent_key'):
                target_agent = parent_meta['agent_key']
                bypass_context = f"User replying to: '{parent_meta.get('content', '...')}'."

        if not target_agent:
            target_agent = await orchestrator.route_request(user_input, current_user)
        
        # LOGGING (SANITIZED)
        # Use shared builder to produce consistent log content and input_type
        log_content, input_type = SessionManager.build_log_content(sensory_payload, sanitized_input, update.message)

        if update.message:
            await SessionManager.add_message(
                chat_id,
                {
                    "role": current_user.role.value,
                    "content": log_content,
                    "user_id": user_id,
                    "name": current_user.name,
                    "message_id": update.message.message_id,
                    "input_type": input_type
                }
            )

        # EJECUCIÓN
        respuesta = await orchestrator.execute_request(
            user_message=user_input, 
            target_agent_key=str(target_agent), 
            chat_id=chat_id, 
            user=current_user,
            extra_context=bypass_context
        )
        respuesta_str = str(respuesta)
        
        sent_msg = await send_smart_response(update, f"🤖 *[{target_agent}]*\n\n{respuesta_str}")

        if sent_msg:
            await SessionManager.add_message(
                chat_id,
                {
                    "role": "assistant", 
                    "content": respuesta_str, 
                    "user_id": context.bot.id, 
                    "name": "LifeOS", 
                    "message_id": sent_msg.message_id,
                    "agent_key": target_agent 
                }
            )
        else:
            logging.warning("⚠️ No se pudo enviar mensaje de respuesta (sent_msg es None).")

    except Exception as e:
        logging.error("Error en proceso: %s", e, exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Error: `{str(e)}`")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.warning(f'Update {update} causó error {context.error}')

# --- Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info(f"🚀 Iniciando LifeOS ({RUN_MODE})...")
    
    cortex = SensoryCortex()
    cortex.register_driver('photo', VisualDriver())
    cortex.register_driver('voice', AudioDriver())
    
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler('start', start))
    bot_app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, chat_logic))
    bot_app.add_error_handler(error_handler)
    
    app.state.bot_app = bot_app
    await bot_app.initialize()
    await bot_app.start()
    
    if RUN_MODE == 'webhook' and WEBHOOK_URL:
        await bot_app.bot.set_webhook(url=f"{WEBHOOK_URL}/telegram")
    else:
        await bot_app.bot.delete_webhook()
        await bot_app.updater.start_polling()
    
    yield
    
    logging.info("🛑 Deteniendo LifeOS...")
    if RUN_MODE != 'webhook':
        await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": RUN_MODE}

@app.post("/telegram")
async def telegram_webhook(request: Request):
    if RUN_MODE != 'webhook': return Response(status_code=404)
    bot_app = request.app.state.bot_app
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return Response(status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)