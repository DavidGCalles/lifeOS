import logging
import asyncio
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.config import load_credentials
# Importamos el NUEVO orquestador basado en CrewAI
from src.crew_orchestrator import CrewOrchestrator 

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logging.getLogger("httpx").setLevel(logging.WARNING)  # Reducir verbosidad de httpx
# --- INICIALIZACIÓN ---
TELEGRAM_TOKEN = load_credentials() # Ya no pedimos la key de Gemini

# Instanciamos el orquestador de Crews (se conecta a LiteLLM automáticamente por tu config)
orchestrator = CrewOrchestrator()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saludo inicial."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔥 LifeOS v2 Online (CrewAI + LiteLLM).\nSistema de agentes distribuido listo. ¿Cuál es el plan?"
    )

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejo del flujo principal:
    Usuario -> Router -> Agente Especialista -> Usuario
    """
    chat_id = update.effective_chat.id
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    
    # 1. Feedback visual: "Escribiendo..."
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # 2. FASE 1: ENRUTAMIENTO (Router Agent)
        # Averiguamos la intención (PADRINO, KITCHEN, CHAT...)
        logging.info(f"Enrutando mensaje: {user_text}")
        # Como crewAI es bloqueante, lo ejecutamos en un thread aparte para no congelar Telegram
        target_agent = await asyncio.to_thread(orchestrator.route_request, user_text)
        
        logging.info(f"Destino decidido: {target_agent}")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing") # Renovamos estado

        # 3. FASE 2: EJECUCIÓN (Specialist Agent)
        # Lanzamos el Crew específico
        respuesta = await asyncio.to_thread(orchestrator.execute_request, user_text, target_agent)

        # 4. Respuesta al usuario
        # Formateamos un poco para saber quién habla
        mensaje_final = f"🤖 *[{target_agent}]*\n\n{respuesta}"
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=mensaje_final, 
            parse_mode='Markdown'
        )

    except Exception as e:
        logging.error(f"Error en el proceso: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Error crítico en el núcleo de los agentes:\n`{str(e)}`",
            parse_mode='Markdown'
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Captura errores de red y otros fallos sin romper el loop."""
    
    # Si es un error de red transitorio, solo lo logueamos como warning y seguimos
    if isinstance(context.error, (NetworkError, TimedOut)):
        logging.warning(f"♻️ Hipoo de conexión con Telegram: {context.error}. Reintentando internamente...")
        return

    # Si es otro tipo de error (bugs de código), lo gritamos
    logging.error(f"⚠️ Excepción no controlada:", exc_info=context.error)

def main():
    """Loop principal de Telegram."""
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_logic))
    app.add_error_handler(error_handler)
    print(">>> 🚀 LifeOS (CrewAI Edition) ESCUCHANDO...")
    app.run_polling()

if __name__ == "__main__":
    main()