import os
from dotenv import load_dotenv

def load_credentials():
    """Carga las credenciales desde el archivo .env."""
    load_dotenv()
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    
    if not gemini_api_key:
        raise ValueError("No se encontró GEMINI_API_KEY en el archivo .env.")
    if not telegram_token:
        raise ValueError("No se encontró TELEGRAM_TOKEN en el archivo .env.")
        
    return gemini_api_key, telegram_token
