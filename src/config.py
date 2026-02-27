'''Configuration management for the application.'''
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

def get_litellm_health_url():
    """
    Returns the URL for the LiteLLM health check.
    """
    load_dotenv()
    return str(os.getenv("LITELLM_URL", "http://litellm:4000")+"/health")
