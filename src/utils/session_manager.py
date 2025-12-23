import json
import os
from typing import Dict

# Configuración
DATA_DIR = os.path.join(os.getcwd(), 'data')
SESSION_FILE = os.path.join(DATA_DIR, 'sessions.json')
MAX_HISTORY = 10  # Ventana deslizante (Memoria de Pez Dorada)

class SessionManager:
    """
    Gestor de persistencia para el contexto conversacional inmediato.
    """

    @staticmethod
    def _ensure_data_dir():
        """Se asegura de que la carpeta data exista."""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    @staticmethod
    def _load_sessions() -> Dict:
        """Carga el JSON de sesiones. Si falla, devuelve dict vacío."""
        SessionManager._ensure_data_dir()
        if not os.path.exists(SESSION_FILE):
            return {}
        
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    @staticmethod
    def _save_sessions(data: Dict):
        """Escritura atómica para evitar corrupciones."""
        SessionManager._ensure_data_dir()
        temp_file = f"{SESSION_FILE}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, SESSION_FILE)
        except Exception as e:
            print(f"❌ Error guardando sesión: {e}")

    @staticmethod
    def get_context(chat_id: int) -> str:
        """
        Devuelve el historial formateado como string para inyectar en el Prompt.
        """
        data = SessionManager._load_sessions()
        chat_key = str(chat_id)
        history = data.get(chat_key, [])
        
        if not history:
            return ""

        # Formato claro para que el LLM distinga quién dijo qué
        context_str = "\n--- 📜 CONTEXTO DE LA CONVERSACIÓN PREVIA ---\n"
        for item in history:
            context_str += f"User: {item['user']}\n"
            context_str += f"AI: {item['ai']}\n"
        context_str += "--- FIN DEL CONTEXTO ---\n"
        
        return context_str

    @staticmethod
    def save_interaction(chat_id: int, user_msg: str, ai_msg: str):
        """
        Guarda el turno y poda el historial si excede el límite.
        """
        data = SessionManager._load_sessions()
        chat_key = str(chat_id)
        
        if chat_key not in data:
            data[chat_key] = []
        
        data[chat_key].append({
            "user": user_msg,
            "ai": ai_msg
        })
        
        # Sliding Window
        if len(data[chat_key]) > MAX_HISTORY:
            data[chat_key] = data[chat_key][-MAX_HISTORY:]
            
        SessionManager._save_sessions(data)