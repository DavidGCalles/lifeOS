'''
LifeOS v2 - Async Fast Track + Sensory Cortex Integration
'''
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from src.config import load_credentials
from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager
from src.identity_manager import IdentityManager, UserRole
from src.utils.tool_context import inject_runtime_context
from src.logging_config import configure_logging

# --- SENSORY IMPORTS ---
from src.sensory import SensoryCortex
from src.sensory.drivers.visual_driver import VisualDriver

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔥 LifeOS v2 Online.\nModo: {RUN_MODE.upper()}")

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user: return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # 1. Identidad
    current_user = await IdentityManager.get_user(user_id)
    # --- 🚧 PROTOCOLO DE INTERCEPCIÓN (PENDING/BLOCKED) 🚧 ---
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
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # 2. SENSORY CORTEX PROCESSING
    # El Córtex decide si hay imagen, texto o nada.
    sensory_payload = await SensoryCortex().process(update)
    
    user_input: str | list[dict[str, Any]] | None = None
    is_multimodal = False

    if sensory_payload:
        # Es una imagen/audio -> Lista de dicts
        user_input = sensory_payload["content"]
        is_multimodal = True
    elif update.message and update.message.text:
        # Es texto plano -> String
        user_input = update.message.text
    else:
        # Nada procesable (Sticker, edit, etc que no manejamos)
        return

    # 3. ENRUTAMIENTO Y EJECUCIÓN
    try:
        target_agent = None
        bypass_context = None

        # Reply-To Check
        if update.message and update.message.reply_to_message:
            parent_id = update.message.reply_to_message.message_id
            parent_meta = await SessionManager.get_message_metadata(chat_id, parent_id)
            if parent_meta and parent_meta.get('agent_key'):
                target_agent = parent_meta['agent_key']
                bypass_context = f"User replying to: '{parent_meta.get('content', '...')}'."

        if not target_agent:
            # El router recibe el input (sea texto o lista)
            target_agent = await orchestrator.route_request(user_input, current_user)
        
        # LOGGING (SANITIZED)
        # No guardamos el base64 en Firestore.
        log_content = user_input
        if is_multimodal and isinstance(user_input, list):
            # Buscamos el caption si existe
            text_part = next((str(x["text"]) for x in user_input if x.get("type") == "text"), "")
            log_content = f"[MULTIMODAL FILE] {text_part}"

        if update.message:
            await SessionManager.add_message(
                chat_id,
                {
                    "role": current_user.role.value, 
                    "content": log_content, 
                    "user_id": user_id, 
                    "name": current_user.name, 
                    "message_id": update.message.message_id
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
        
        # Enviar respuesta
        try:
            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🤖 *[{target_agent}]*\n\n{respuesta_str}",
                parse_mode='Markdown'
            )
        except Exception:
            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🤖 [{target_agent}]\n\n{respuesta_str}"
            )

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

    except Exception as e:
        logging.error("Error en proceso: %s", e, exc_info=True)
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Error: `{str(e)}`")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.warning(f'Update {update} causó error {context.error}')

# --- Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info(f"🚀 Iniciando LifeOS ({RUN_MODE})...")
    
    # INICIALIZACIÓN SENSORIAL
    cortex = SensoryCortex()
    cortex.register_driver('photo', VisualDriver())
    
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler('start', start))
    # Aceptamos TEXTO y FOTOS
    bot_app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, chat_logic))
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