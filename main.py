'''
LifeOS v2 - Async Fast Track Edition (FastAPI Wrapper + Polling Support)
'''
import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.config import load_credentials
from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager
from src.identity_manager import IdentityManager, UserRole
from src.utils.tool_context import inject_runtime_context

# Configuración de Logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Configuración
TELEGRAM_TOKEN = load_credentials()
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
RUN_MODE = os.getenv('RUN_MODE', 'polling').lower() # Default a polling en local
PORT = int(os.getenv('PORT', '8080')) 
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID') 

session_manager = SessionManager()
orchestrator = CrewOrchestrator(session_manager=session_manager)

# --- Lógica del Bot (Handlers) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🔥 LifeOS v2 Online (Async + FastAPI).\nModo: {RUN_MODE.upper()}"
    )

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not update.message or not update.message.text:
        return

    # 1. Identidad
    current_user = await IdentityManager.get_user(user_id)
    
    # --- 🚧 THE TRAP (INTERCEPTION PROTOCOL) 🚧 ---
    if current_user.role == UserRole.BLOCKED:
        logging.info(f"🚫 Blocked user {user_id} attempted contact. Silenced.")
        return # Fallo silencioso. No gastamos cómputo ni ancho de banda.

    if current_user.role == UserRole.PENDING:
        # 1. Capturar metadatos para el dossier
        username = update.effective_user.username or "NoUsername"
        first_name = update.effective_user.first_name or "Unknown"
        
        logging.warning(f"🚨 INTRUSION DETECTED: {first_name} (@{username}) - ID: {user_id}")

        # 2. Actualizar el contexto en memoria para el registro
        current_user.name = first_name
        current_user.description = f"@{username}" # Guardamos el handle como descripción
        
        # 3. Fichar al sujeto en Firestore (para poder promoverlo luego)
        await IdentityManager.register_user(current_user)
        
        # 4. Notificar al Intruso (Protocolo de Seguridad)
        await context.bot.send_message(
            chat_id=chat_id, 
            text="🛡️ **Security Protocol Active**\n\nIdentity verification required. Access is restricted pending Administrator approval.",
            parse_mode='Markdown'
        )
        
        # 5. Alertar al SOBERANO (Tú)
        if ADMIN_USER_ID:
            alert_text = (
                f"🚨 **INTRUSION ALERT**\n\n"
                f"**Name:** {first_name}\n"
                f"**Handle:** @{username}\n"
                f"**ID:** `{user_id}`\n\n"
                f"To authorize, reply:\n"
                f"`Authorize {user_id} as FAMILY`"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=alert_text, parse_mode='Markdown')
            except Exception as e:
                logging.error(f"❌ Failed to send alert to ADMIN_USER_ID: {e}")
        
        return # 🛑 DETENER EJECUCIÓN AQUÍ. No invocar agentes.
    
    # --- END TRAP ---

    logging.info("👤 User: %s (%s)", current_user.name, current_user.role)

    # 2. Inyección de Contexto en Herramientas
    inject_runtime_context(current_user)

    # Nota: Eliminamos el check antiguo de GUEST porque PENDING ya cubre ese caso.
    # Los roles EXTERNAL o GUEST (si se asignan manualmente) pasarán a los agentes,
    # y será el agente quien decida si tiene permisos para usar herramientas sensibles.

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # FASE 1: ENRUTAMIENTO
        target_agent = await orchestrator.route_request(user_text, current_user)
        logging.info("Enrutando: %s -> %s", user_text, target_agent)
        
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # LOGGING USER
        await SessionManager.add_message(
            chat_id,
            {"role": current_user.role.value, "content": user_text, "user_id": current_user.telegram_id, "name": current_user.name, "message_id": update.message.message_id}
        )

        # FASE 2: EJECUCIÓN
        respuesta = await orchestrator.execute_request(user_text, target_agent, chat_id, current_user)
        respuesta_str = str(respuesta)
        
        # FASE 3: RESPUESTA
        final_text = f"🤖 *[{target_agent}]*\n\n{respuesta_str}"

        try:
            # Intento 1: Enviar con Markdown (bonito)
            sent_message = await context.bot.send_message(
                chat_id=chat_id,
                text=final_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.warning(f"⚠️ Markdown Error: {e}. Falling back to plain text.")
            # Intento 2: Fallback a Texto Plano (seguro)
            clean_text = f"🤖 [{target_agent}]\n\n{respuesta_str}"
            sent_message = await context.bot.send_message(
                chat_id=chat_id,
                text=clean_text,
                parse_mode=None
            )

        # LOGGING BOT
        await SessionManager.add_message(
            chat_id,
            {"role": "assistant", "content": respuesta_str, "user_id": context.bot.id, "name": "LifeOS", "message_id": sent_message.message_id}
        )

    except Exception as e:
        logging.error("Error en el proceso: %s", e)
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Error crítico:\n`{str(e)}`", parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.warning(f'Update {update} caused error {context.error}')

# --- FastAPI Setup & Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logging.info(f"🚀 Iniciando LifeOS ({RUN_MODE})...")
    
    # Construimos la app de Telegram
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler('start', start))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_logic))
    bot_app.add_error_handler(error_handler)
    
    # Inyectamos en estado para acceso global
    app.state.bot_app = bot_app
    
    await bot_app.initialize()
    await bot_app.start()
    
    if RUN_MODE == 'webhook' and WEBHOOK_URL:
        # MODO NUBE: Configuramos Webhook
        webhook_path = f"{WEBHOOK_URL}/telegram"
        logging.info(f"🔗 Configurando Webhook: {webhook_path}")
        await bot_app.bot.set_webhook(url=webhook_path)
    else:
        # MODO LOCAL (DOCKER): Arrancamos Polling manual
        logging.info("📡 Arrancando Polling (Modo Local)...")
        # Eliminamos cualquier webhook previo para evitar conflictos
        await bot_app.bot.delete_webhook()
        await bot_app.updater.start_polling()
    
    yield # La aplicación corre aquí
    
    # --- SHUTDOWN ---
    logging.info("🛑 Deteniendo LifeOS...")
    if RUN_MODE != 'webhook':
        await bot_app.updater.stop()
        
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

# Health Check
@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": RUN_MODE}

# Webhook Handler
@app.post("/telegram")
async def telegram_webhook(request: Request):
    if RUN_MODE != 'webhook':
        return Response(status_code=404, content="Webhook disabled in polling mode")
        
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