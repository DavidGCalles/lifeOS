import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

# 1. Carga las variables de entorno (busca archivo .env o variables del sistema)
load_dotenv()

# Recuperamos la Key
api_key = os.getenv("GEMINI_API_KEY")

# VERIFICACIÓN DE SEGURIDAD
if not api_key:
    print("❌ ERROR CRÍTICO: No se encontró la variable 'GOOGLE_API_KEY'.")
    print("Asegúrate de tener un archivo .env con: GOOGLE_API_KEY=tu_clave_aqui")
    print("O exporta la variable en tu terminal.")
    exit(1)

# Configuramos la librería
genai.configure(api_key=api_key)

# 2. La lista LIMPIA filtrada de tu JSON (Solo modelos de chat/texto)
candidates_list = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-pro",
    "models/gemini-2.0-flash-exp",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-001",
    "models/gemini-2.0-flash-lite-001",
    "models/gemini-2.0-flash-lite",
    "models/gemini-2.0-flash-lite-preview-02-05",
    "models/gemini-2.0-flash-lite-preview",
    "models/gemini-exp-1206",
    "models/gemma-3-1b-it",
    "models/gemma-3-4b-it",
    "models/gemma-3-12b-it",
    "models/gemma-3-27b-it",
    "models/gemma-3n-e4b-it",
    "models/gemma-3n-e2b-it",
    "models/gemini-flash-latest",
    "models/gemini-flash-lite-latest",
    "models/gemini-pro-latest",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-flash-preview-09-2025",
    "models/gemini-2.5-flash-lite-preview-09-2025",
    "models/gemini-3-pro-preview",
    "models/gemini-3-flash-preview",
    "models/deep-research-pro-preview-12-2025"
]

valid_models = []
failed_models = []

print(f"🚀 Iniciando validación de {len(candidates_list)} modelos contra tu API Key...")
print("-" * 50)

for model_name in candidates_list:
    try:
        # Instanciamos el modelo
        model = genai.GenerativeModel(model_name)
        
        # Hacemos una llamada mínima (1 token) para validar acceso
        # Usamos 'Hola' simple. Si falla aquí, es que la Key no tiene permiso o el modelo no existe.
        response = model.generate_content(
            "Hola", 
            generation_config={"max_output_tokens": 1}
        )
        
        print(f"✅ [VIVO] {model_name}")
        valid_models.append(model_name)
        
    except Exception as e:
        error_msg = str(e)
        
        # Filtramos un poco el error para que sea legible
        if "404" in error_msg or "Not Found" in error_msg:
            print(f"❌ [404]  {model_name} (No disponible para tu Key)")
        elif "429" in error_msg:
            print(f"⚠️ [429]  {model_name} (Rate Limit - El modelo existe pero estás limitado)")
            # Si es rate limit, técnicamente es válido, pero falló la llamada.
            # Lo añado a válidos con asterisco mental o lo reintento.
            # Para este script, lo marcamos como fallo temporal.
        else:
            print(f"💀 [ERR]  {model_name} -> {error_msg.split(' ')[0]}...") # Error corto
            
        failed_models.append(model_name)

    # PEQUEÑA PAUSA para no provocar nosotros mismos un Rate Limit por ir a metralleta
    time.sleep(0.5) 

print("-" * 50)
print(f"\n📊 RESUMEN FINAL:")
print(f"Modelos Funcionales: {len(valid_models)}")
print(f"Modelos Fallidos:    {len(failed_models)}")

if valid_models:
    print("\n📋 Copia esta lista para tu app (Python List):")
    print(valid_models)
else:
    print("\n⚠️ Ningún modelo respondió. Revisa tu API Key o tu conexión.")