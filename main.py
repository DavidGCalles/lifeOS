'''
LifeOS v2 - Async Fast Track Edition
'''
import logging
import asyncio
import os
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.config import load_credentials
from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager
from src.identity_manager import IdentityManager, UserRole
from src.tools import TOOL_MAPPING

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_TOKEN = load_credentials()
RUN_MODE = os.getenv('RUN_MODE', 'polling')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
WEBHOOK_PORT = int(os.getenv('PORT', '8080'))

session_manager = SessionManager()
orchestrator = CrewOrchestrator(session_manager=session_manager)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔥 LifeOS v2 Online (Async Engine).\nSistema de latencia optimizada listo."
    )

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not update.message or not update.message.text:
        return

    # 1. Identidad
    current_user = await asyncio.to_thread(IdentityManager.get_user, user_id)
    logging.info("👤 User: %s (%s)", current_user.name, current_user.role)

    if 'save_memory' in TOOL_MAPPING:
        TOOL_MAPPING['save_memory'].set_context(current_user)

    if current_user.role == UserRole.GUEST:
        await context.bot.send_message(chat_id=chat_id, text="⛔ Acceso Denegado.")
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # FASE 1: ENRUTAMIENTO (NATIVO ASYNC)
        # Ya no usamos asyncio.to_thread aquí, el orchestrator maneja la asincronía
        logging.info("Enrutando mensaje: %s", user_text)
        
        target_agent = await orchestrator.route_request(
            user_text,
            current_user
        )

        logging.info("Destino decidido: %s", target_agent)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        await asyncio.to_thread(
            SessionManager.add_message,
            chat_id,
            {
                "role": current_user.role.value,
                "content": user_text,
                "user_id": current_user.telegram_id,
                "name": current_user.name,
                "message_id": update.message.message_id
            }
        )

        # FASE 2: EJECUCIÓN (NATIVO ASYNC)
        # JANE/DISPATCHER responderán en <1s. PADRINO usará un hilo de fondo.
        respuesta = await orchestrator.execute_request(
            user_text,
            target_agent,
            chat_id,
            current_user
        )

        # FASE 3: RESPUESTA
        respuesta_str = str(respuesta)
        mensaje_final = f"🤖 *[{target_agent}]*\n\n{respuesta_str}"
        
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje_final,
            parse_mode='Markdown'
        )

        await asyncio.to_thread(
            SessionManager.add_message,
            chat_id,
            {
                "role": "assistant",
                "content": respuesta_str,
                "user_id": context.bot.id,
                "name": "LifeOS",
                "message_id": sent_message.message_id
            }
        )

    except Exception as e:
        logging.error("Error en el proceso: %s", e)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Error crítico:\n`{str(e)}`",
            parse_mode='Markdown'
        )

def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.warning(f'Update {update} caused error {context.error}')

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_logic))
    app.add_error_handler(error_handler)
    print("🤖 LifeOS v2 Bot iniciando (Async Mode).")
    
    if RUN_MODE == 'WEBHOOK':
        if not WEBHOOK_URL:
            logging.error("❌ FATAL: RUN_MODE=webhook pero PUBLIC_URL no está definida.")
            sys.exit(1)
        app.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            url_path="telegram",
            webhook_url=f"{WEBHOOK_URL}/telegram"
        )
    else:
        logging.info("🚀 Iniciando en modo POLLING.")
        app.run_polling()

if __name__ == "__main__":
    main()