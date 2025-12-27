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
    
    # ---------------------------------------------------------
    # EL RADAR VISUAL (Mira tu consola)
    # ---------------------------------------------------------
    print("\n" + "█"*50)
    print(f"🎯 OBJETIVO DETECTADO")
    print(f"👤 Nombre:   {user.first_name} {user.last_name or ''}")
    print(f"🏷️ Username: @{user.username}")
    print(f"🆔 USER ID:  {user.id}  <--- COPIA ESTE NÚMERO")
    print(f"💬 Chat ID:  {chat.id} ({chat.type})")
    print("█"*50 + "\n")

    # Feedback para el usuario (opcional, para que sepan que el bot "oye")
    await update.message.reply_text(
        f"👮‍♂️ **Identity Radar**\n\nTu ID es: `{user.id}`", 
        parse_mode="Markdown"
    )

def run_radar():
    if not TOKEN:
        print("❌ ERROR: No encuentro TELEGRAM_BOT_TOKEN en el .env")
        sys.exit(1)

    print(f"🛰️  RADAR INICIADO con token: {TOKEN[:5]}...*****")
    print("👉 Manda un mensaje al bot desde Telegram ahora.")
    print("👉 Pulsa Ctrl+C para salir.\n")

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
        print("\n👋 Radar apagado.")