import google.generativeai as genai
from google.api_core import exceptions
from src.prompts.prompts import PADRINO_SYSTEM_PROMPT

class PadrinoAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.user_histories = {}
        self.name = "[🚬 Padrino]"
        self.system_prompt = PADRINO_SYSTEM_PROMPT
        self.model_chain = [
            'gemini-2.5-flash',       # El Ferrari (20/día)
            'gemini-2.5-flash-lite',  # El Repuesto (20/día)
            'gemma-3-27b-it',         # El Tanque Pesado (14.4k/día) - "it" es "instruction tuned"
            'gemma-3-12b-it',         # El Tanque Ligero (14.4k/día)
        ]

    def clear_history(self, chat_id: int):
        self.user_histories[chat_id] = []

    def generate_response(self, chat_id: int, user_text: str) -> tuple[str, str]:
        history = self.user_histories.get(chat_id, [])
        for model_name in self.model_chain:
            try:
                print(f"INTENTANDO CON: {model_name}...")
                # --- PARCHE PARA GEMMA (No soporta system_instruction nativo) ---
                if "gemma" in model_name:
                    # 1. Instanciamos SIN system_instruction
                    model = genai.GenerativeModel(model_name=model_name)
                    # 2. Si el historial está vacío, inyectamos la personalidad manualmente
                    # Simulamos que tú ya se lo has dicho y él ha aceptado.
                    if not history:
                        history = [
                            {"role": "user", "parts": [self.system_prompt]},
                            {"role": "model", "parts": ["Entendido. Soy el Padrino. Corto y cambio."]}
                        ]
                    chat = model.start_chat(history=history)
                # --- LÓGICA ESTÁNDAR PARA GEMINI ---
                else:
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=self.system_prompt
                    )
                    chat = model.start_chat(history=history)
                
                # Fuego
                response = chat.send_message(user_text)
                
                # Guardamos historial actualizado
                self.user_histories[chat_id] = chat.history
                return response.text, model_name, self.name
                
            except exceptions.ResourceExhausted:
                print(f"⚠ {model_name} AGOTADO. Saltando...")
                continue
            except Exception as e:
                print(f"⚠ Error en {model_name}: {e}")
                continue

        return "⚠ ERROR CRÍTICO: Google ha caído. Estamos solos.", "Ninguno"
