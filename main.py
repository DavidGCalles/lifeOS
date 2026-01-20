'''
LifeOS v2 - Async Fast Track Edition (FastAPI Wrapper)
'''
import logging
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.config import load_credentials
from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager
from src.identity_manager import IdentityManager, UserRole
from src.tools import TOOL_MAPPING

# Configuración de Logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
# Silenciamos logs ruidosos de librerías externas
logging.getLogger("httpx").setLevel(logging.WARNING)

# Configuración
TELEGRAM_TOKEN = load_credentials()
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
# Cloud Run inyecta PORT, uvicorn lo usará al arrancar
PORT = int(os.getenv('PORT', '8080')) 

session_manager = SessionManager()
orchestrator = CrewOrchestrator(session_manager=session_manager)

# --- Lógica del Bot (Handlers) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔥 LifeOS v2 Online (Async Engine + FastAPI).\nSistema estable."
    )

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (Lógica idéntica a tu versión anterior) ...
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not update.message or not update.message.text:
        return

    # 1. Identidad
    current_user = await IdentityManager.get_user(user_id)
    logging.info("👤 User: %s (%s)", current_user.name, current_user.role)

    if 'save_memory' in TOOL_MAPPING:
        TOOL_MAPPING['save_memory'].set_context(current_user)

    if current_user.role == UserRole.GUEST:
        await context.bot.send_message(chat_id=chat_id, text="⛔ Acceso Denegado.")
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # FASE 1: ENRUTAMIENTO
        logging.info("Enrutando mensaje: %s", user_text)
        target_agent = await orchestrator.route_request(user_text, current_user)
        logging.info("Destino decidido: %s", target_agent)
        
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # LOGGING USER MESSAGE
        await SessionManager.add_message(
            chat_id,
            {"role": current_user.role.value, "content": user_text, "user_id": current_user.telegram_id, "name": current_user.name, "message_id": update.message.message_id}
        )

        # FASE 2: EJECUCIÓN
        respuesta = await orchestrator.execute_request(user_text, target_agent, chat_id, current_user)
        respuesta_str = str(respuesta)
        
        # FASE 3: RESPUESTA
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=f"🤖 *[{target_agent}]*\n\n{respuesta_str}",
            parse_mode='Markdown'
        )

        # LOGGING BOT MESSAGE
        await SessionManager.add_message(
            chat_id,
            {"role": "assistant", "content": respuesta_str, "user_id": context.bot.id, "name": "LifeOS", "message_id": sent_message.message_id}
        )

    except Exception as e:
        logging.error("Error en el proceso: %s", e)
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Error crítico:\n`{str(e)}`", parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.warning(f'Update {update} caused error {context.error}')

# --- FastAPI Setup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicializar Webhook de Telegram
    logging.info("🚀 Iniciando LifeOS Bot Application...")
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler('start', start))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_logic))
    bot_app.add_error_handler(error_handler)
    
    # Inyectamos la app de telegram en el estado de FastAPI para accederla en las rutas
    app.state.bot_app = bot_app
    
    await bot_app.initialize()
    await bot_app.start()
    
    # Configurar Webhook real
    if WEBHOOK_URL:
        webhook_path = f"{WEBHOOK_URL}/telegram"
        logging.info(f"🔗 Configurando Webhook en: {webhook_path}")
        await bot_app.bot.set_webhook(url=webhook_path)
    
    yield # Aquí corre la aplicación
    
    # Shutdown: Limpieza
    logging.info("🛑 Deteniendo LifeOS Bot Application...")
    await bot_app.stop()
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

# 1. Health Check (Vital para Cloud Run)
@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "lifeos-v2"}

# 2. Webhook Handler
@app.post("/telegram")
async def telegram_webhook(request: Request):
    bot_app = request.app.state.bot_app
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        # Procesar update en el loop de eventos sin bloquear
        await bot_app.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return Response(status_code=500)

if __name__ == "__main__":
    # Solo para desarrollo local sin docker
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)