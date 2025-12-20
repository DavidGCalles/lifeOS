import os
from crewai import LLM

# Configuración para conectar con tu contenedor local de LiteLLM
# Usamos la clase LLM nativa de CrewAI, sin LangChain.

llm = LLM(
    # 'openai/' indica a LiteLLM que use el protocolo estándar de OpenAI (que es lo que habla tu proxy)
    # 'crewai-proxy' es el nombre que definiste en tu litellm_config.yaml
    model="openai/crewai-proxy", 
    
    # URL de tu servicio LiteLLM dentro de Docker
    base_url=os.getenv("LITELLM_URL", "http://litellm:4000"),
    
    # Clave dummy (necesaria por protocolo, pero no se valida externamente)
    api_key="sk-fake-key"
)