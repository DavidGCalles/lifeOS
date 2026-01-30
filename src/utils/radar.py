import os
import requests
import logging

logger = logging.getLogger(__name__)

def available_models():
    """
    Consulta al Proxy LiteLLM para ver qué modelos están activos y disponibles.
    Equivale a listar los modelos de la 'munición' actual.
    """
    # 1. Definimos dónde está el objetivo (el proxy)
    # Por defecto en Docker es http://litellm:4000
    base_url = os.getenv("LITELLM_URL", "http://litellm:4000")
    target_url = f"{base_url}/v1/models"
    
    logger.info(f"\n>>> 📡 RADAR: Escaneando modelos en {base_url}...")

    try:
        # 2. Lanzamos el ping al endpoint estándar de OpenAI
        # LiteLLM requiere una key en la cabecera, aunque sea falsa, para validar el formato HTTP
        headers = {"Authorization": "Bearer sk-radar-ping"}
        
        response = requests.get(target_url, headers=headers, timeout=2)
        response.raise_for_status() # Lanza excepción si hay error 400/500
        
        # 3. Procesamos la inteligencia recibida
        data = response.json()
        models = data.get("data", [])
        
        if not models:
            logger.warning("⚠ ALERTA: El proxy responde, pero no reporta modelos activos.")
            return

        logger.info(f"✅ ENLACE ESTABLECIDO. Arsenal disponible:")
        for m in models:
            # 'id' es el nombre del modelo que debes usar en tu código (ej: openai/crewai-proxy)
            model_id = m.get("id", "Desconocido")
            logger.info(f"   🔹 {model_id}")
            
    except requests.exceptions.ConnectionError:
        logger.error(f"🔥 ERROR DE CONEXIÓN: El proxy en {base_url} no responde.")
        logger.warning("   -> Verifica que el contenedor 'litellm' esté corriendo.")
    except Exception as e:
        logger.error(f"❌ FALLO EN EL ESCANEO: {e}")
    
    logger.info(">>> RADAR FINALIZADO.\n")

if __name__ == "__main__":
    # Para probarlo individualmente desde consola
    available_models()