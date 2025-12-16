import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.config import load_credentials
from src.agents.orchestrator_agent import OrchestratorAgent
from src.utils import available_models

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- INICIALIZACIÓN DEL CEREBRO ---
# Nota: Esto fallará hasta que corrijamos config.py y el .env
GEMINI_API_KEY, TELEGRAM_TOKEN = load_credentials()
orchestrator = OrchestratorAgent(GEMINI_API_KEY)

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja el comando /start, iniciando una nueva conversación."""
    orchestrator.start_chat(update.effective_chat.id)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Sistema Online. Arquitectura de Fallback activa. Tengo munición infinita. Desahógate."
    )

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa los mensajes de texto del usuario."""
    chat_id = update.effective_chat.id

    if not update.message or not update.message.text:
        logging.info("Update received with no message text.")
        return

    text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Derivar al orquestador para obtener una respuesta
    respuesta, modelo_usado, nombre_agente = orchestrator.route(chat_id, text)
    # Enviar la respuesta de vuelta al usuario
    respuesta_final = f"[{nombre_agente}]\n\n{respuesta}\n\n_🔧 Procesado por: {modelo_usado}_"
    await context.bot.send_message(chat_id=chat_id, text=respuesta_final, parse_mode='Markdown')

def main():
    """Inicia el bot de Telegram y se queda escuchando."""
    available_models()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    # Añadir manejadores de comandos y mensajes
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_logic))
    print(">>> PADRINO INMORTAL ESCUCHANDO...")
    app.run_polling()

if __name__ == "__main__":
    main()
