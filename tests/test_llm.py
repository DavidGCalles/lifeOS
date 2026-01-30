'''
Docstring for test_llm
'''
import os
import sys
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN ---
# 1. ¿Dónde está escuchando tu servicio de LiteLLM?
# Si estás dentro de docker, suele ser http://litellm:4000/v1 o el nombre del servicio en el compose.
BASE_URL = os.getenv("LITELLM_URL", "http://litellm:4000") 

# 2. La API Key 'falsa'. 
# Al conectar con LiteLLM local, a veces requiere una string cualquiera para no fallar la validación del cliente,
# aunque la auth real la hace el servicio con Google.
API_KEY = "sk-cualquier-cosa-porque-usamos-litellm"

logger.info(f"--- Test de Conexión: Cliente OpenAI -> Servicio LiteLLM ({BASE_URL}) ---")

try:
    # 3. Iniciamos el cliente OFICIAL de OpenAI
    # Le decimos: "No vayas a los servidores de OpenAI, ve a mi servicio local".
    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL
    )

    # 4. Llamada estándar. 
    # El modelo aquí debe coincidir con el alias que le hayas puesto en tu config de LiteLLM.
    # Si en LiteLLM mapeaste "gemini-flash" a google/gemini-1.5-flash, usa "gemini-flash".
    # Si no mapeaste nada, usa el nombre real: "gemini/gemini-1.5-flash"
    MODELO_A_PROBAR = "gemini/gemini-2.5-flash" 

    response = client.chat.completions.create(
        model=MODELO_A_PROBAR,
        messages=[
            {"role": "user", "content": "Hola, ¿me recibes? Responde 'SÍ' y tu modelo."}
        ]
    )

    # 5. Resultado
    logger.info("✅ CONEXIÓN EXITOSA")
    logger.info("Respuesta: %s", response.choices[0].message.content)

except Exception as e:
    logger.error("🔥 FALLO DE CONEXIÓN")
    logger.error("Error: %s", e)
    logger.error("\nPosibles causas:")
    logger.error("1. El servicio de LiteLLM no está corriendo o no es accesible en esa URL.")
    logger.error("2. El nombre del modelo no coincide con lo que LiteLLM espera.")
    sys.exit(1)