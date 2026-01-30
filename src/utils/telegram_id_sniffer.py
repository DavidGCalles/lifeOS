import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes




async def radar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Interrcepta TODO y escupe la ficha técnica.
    """
    if not update.effective_user:
        return

    user = update.effective_user
    chat = update.effective_chat
    
    import logging
    logger = logging.getLogger(__name__)
    # ---------------------------------------------------------
    # EL RADAR VISUAL (Mira tu consola)
    # ---------------------------------------------------------
    logger.info("\n" + "█"*50)
    logger.info(f"🎯 OBJETIVO DETECTADO")
    logger.info(f"👤 Nombre:   {user.first_name} {user.last_name or ''}")
    logger.info(f"🏷️ Username: @{user.username}")
    logger.info(f"🆔 USER ID:  {user.id}  <--- COPIA ESTE NÚMERO")
    logger.info(f"💬 Chat ID:  {chat.id} ({chat.type})")
    logger.info("█"*50 + "\n")

    # Feedback para el usuario (opcional, para que sepan que el bot "oye")
    await update.message.reply_text(
        f"👮‍♂️ **Identity Radar**\n\nTu ID es: `{user.id}`", 
        parse_mode="Markdown"
    )

def run_radar():
    import logging
    logger = logging.getLogger(__name__)

    if not TOKEN:
        logger.error("❌ ERROR: No encuentro TELEGRAM_BOT_TOKEN en el .env")
        sys.exit(1)

    logger.info(f"🛰️  RADAR INICIADO con token: {TOKEN[:5]}...*****")
    logger.info("👉 Manda un mensaje al bot desde Telegram ahora.")
    logger.info("👉 Pulsa Ctrl+C para salir.\n")

    # Construimos la app mínima
    app = Application.builder().token(TOKEN).build()
    
    # Escuchamos TODO (Texto, Fotos, Audio, Comandos...)
    app.add_handler(MessageHandler(filters.ALL, radar_handler))

    # A rodar
    app.run_polling()

if __name__ == "__main__":
    try:
        # Ajusta esto si tu .env está en otro sitio
        load_dotenv("../../.env")
        TOKEN = os.getenv("TELEGRAM_TOKEN", "")
        run_radar()
    except KeyboardInterrupt:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("\n👋 Radar apagado.")