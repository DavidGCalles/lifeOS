import os
from dotenv import load_dotenv

def load_credentials():
    """
    Carga las credenciales.
    """
    load_dotenv()
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    
    if not telegram_token:
        raise ValueError("❌ CRÍTICO: No se encontró TELEGRAM_TOKEN en el .env")
        
    return telegram_token