'''
Docstring for src.llm_config
'''
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import load_credentials

# Cargamos credenciales
GEMINI_API_KEY, _ = load_credentials()
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# Configuración común para todos los modelos
common_config = {
    "google_api_key": GEMINI_API_KEY,
    "temperature": 0.7,
    "max_retries": 1, # No reintentar demasiado el mismo modelo, saltar rápido al siguiente
}

# --- DEFINICIÓN DE LA CADENA DE MODELOS (Tu "Chain of Responsibility") ---

# 1. El Ferrari (Rápido, pero rate limit estricto)
primary_model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    **common_config
)

# 2. El Repuesto (Versión Lite)
fallback_1 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    **common_config
)

# 3. El Tanque Pesado (Gemma 27b - Instruction Tuned)
fallback_2 = ChatGoogleGenerativeAI(
    model="gemma-3-27b-it",
    **common_config
)

# 4. El Tanque Ligero (Gemma 12b - Último recurso)
fallback_3 = ChatGoogleGenerativeAI(
    model="gemma-3-12b-it",
    **common_config
)

# --- ENSAMBLAJE DEL LLM RESILIENTE ---
# Creamos un objeto que se comporta como un LLM único, pero internamente
# gestiona la cascada de errores.
llm = primary_model.with_fallbacks([fallback_1, fallback_2, fallback_3])

# (Opcional) Un manager "más listo" para decisiones complejas si fuera necesario,
# aunque para este caso el 'llm' de arriba sirve para todo.
manager_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    **common_config
)
