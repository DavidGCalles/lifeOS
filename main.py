'''
LifeOS v2 - CrewAI Edition
'''
import logging
import asyncio
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.config import load_credentials
# Importamos el orquestador
from src.crew_orchestrator import CrewOrchestrator
from src.utils.session_manager import SessionManager

# --- NUEVOS IMPORTS PARA IDENTIDAD ---
from src.identity_manager import IdentityManager, UserRole
from src.tools import TOOL_MAPPING

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Reducir verbosidad de httpx

# --- INICIALIZACIÓN ---
TELEGRAM_TOKEN = load_credentials()
# --- Gestor de Sesión ---
# El factory devolverá la instancia correcta (JSON o Firestore)
session_manager = SessionManager()
orchestrator = CrewOrchestrator(session_manager=session_manager)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saludo inicial."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔥 LifeOS v2 Online (CrewAI + LiteLLM).\nSistema de agentes distribuido listo. ¿Cuál es el plan?"
    )

async def chat_logic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejo del flujo principal:
    Usuario -> Identidad -> Router -> Agente Especialista -> Usuario
    """
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id  # ID crudo de Telegram

    if not update.message or not update.message.text:
        return

    # --- 🛡️ CAPA DE IDENTIDAD (MIDDLEWARE) ---
    # 1. Resolvemos quién es el usuario consultando users.json
    current_user = IdentityManager.get_user(user_id)
    logging.info("👤 User: %s (%s)", current_user.name, current_user.role)

    # 2. Inyección de Contexto de usuario en las Tools (Global State)
    # CUIDADO, naive: esto es un state global, no por instancia
    if 'save_memory' in TOOL_MAPPING:
        TOOL_MAPPING['save_memory'].set_context(current_user)

    # 3. Bloqueo de seguridad para desconocidos
    if current_user.role == UserRole.GUEST:
        await context.bot.send_message(chat_id=chat_id, text="⛔ Acceso Denegado.")
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # FASE 1: ENRUTAMIENTO (Router Agent)
        # Averiguamos la intención inyectando la identidad (para matices de contexto)
        logging.info("Enrutando mensaje: %s", user_text)
        target_agent = await asyncio.to_thread(
            orchestrator.route_request,
            user_text,
            current_user
        )

        logging.info("Destino decidido: %s", target_agent)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # FASE 2: EJECUCIÓN (Specialist Agent)
        # Lanzamos el Crew específico inyectando Identidad + Memoria
        respuesta = await asyncio.to_thread(
            orchestrator.execute_request,
            user_text,
            target_agent,
            chat_id,
            current_user
        )

        # FASE 3: PERSISTENCIA (Chat History Local)
        # Guardamos el turno para la "memoria de pez" (SessionManager)
        # Esto permite mantener el hilo de la conversación inmediata
        respuesta_str = str(respuesta)
        session_manager.save_interaction(chat_id, user_text, respuesta_str)

        # 4. Respuesta al usuario
        mensaje_final = f"🤖 *[{target_agent}]*\n\n{respuesta}"
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje_final,
            parse_mode='Markdown'
        )

    except Exception as e:
        logging.error("Error en el proceso: %s", e)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Error crítico en el núcleo de los agentes:\n`{str(e)}`",
            parse_mode='Markdown'
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Captura errores de red y otros fallos sin romper el loop."""
    # Si es un error de red transitorio, solo lo logueamos como warning y seguimos
    if isinstance(context.error, (NetworkError, TimedOut)):
        logging.warning("♻️ Hipo de conexión con Telegram: %s. Reintentando internamente...", context.error)
        return

    # Si es otro tipo de error (bugs de código)
    logging.error("⚠️ Excepción no controlada:", exc_info=context.error)
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
