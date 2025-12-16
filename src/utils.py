import google.generativeai as genai

def available_models() -> None:
    # Asegúrate de que esto corre DESPUÉS de tu genai.configure(api_key=...)
    print("\n>>> ESCANEANDO MODELOS DISPONIBLES EN TU CUENTA...")

    try:
        for m in genai.list_models():
            # Filtramos solo los que generan texto/chat
            if 'generateContent' in m.supported_generation_methods:
                print(f"🔹 {m.name}")
                # Descomenta esto si quieres ver los límites de tokens:
                # print(f"   Limits: In={m.input_token_limit} / Out={m.output_token_limit}")
    except Exception as e:
        print(f"⚠ Error al listar modelos: {e}")
    print(">>> ESCANEO FINALIZADO.\n")

#available_models()