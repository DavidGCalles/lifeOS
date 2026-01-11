import json
import os
import sys
from abc import ABC, abstractmethod
from typing import Any

from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# --- Constants ---
DATA_DIR = os.path.join(os.getcwd(), 'data')
SESSION_FILE = os.path.join(DATA_DIR, 'sessions.json')
MAX_HISTORY = 10

# --- Environment Configuration ---
USE_FIRESTORE = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
FIRESTORE_DB_NAME = os.getenv('FIRESTORE_DB_NAME')

# --- Firestore Client Initialization ---
db = None
if USE_FIRESTORE:
    try:
        if USE_FIRESTORE and FIRESTORE_DB_NAME is None:
            print("⚠️  WARNING: USE_FIRESTORE is set to True but FIRESTORE_DB_NAME is not defined.")
            print("Falling back to default database.")
        import google.cloud.firestore
        # This will use the GOOGLE_APPLICATION_CREDENTIALS environment variable
        db = google.cloud.firestore.Client(database=FIRESTORE_DB_NAME)
        print("✅ Cliente de Firestore inicializado correctamente.")
    except ImportError:
        print("❌ Error: La biblioteca 'google-cloud-firestore' no está instalada.")
        print("Por favor, ejecute: pip install google-cloud-firestore")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al inicializar Firestore: {e}")
        print("Asegúrese de que GOOGLE_APPLICATION_CREDENTIALS esté configurado correctamente.")
        # Fail gracefully in local, but exit if in prod-like environment
        if os.getenv('CI'): # Simple check for a prod-like environment
            sys.exit(1)

# --- Base Session Manager ---
class BaseSessionManager(ABC):
    """
    Clase base abstracta para los gestores de sesión.
    Define la interfaz que deben seguir todos los gestores.
    """
    @abstractmethod
    def get_context(self, chat_id: int) -> str:
        ...

    @abstractmethod
    def save_interaction(self, chat_id: int, user_msg: str, ai_msg: str):
        ...

# --- JSON File Session Manager (Local) ---
class JSONSessionManager(BaseSessionManager):
    """
    Gestor de persistencia para el contexto conversacional inmediato usando un archivo JSON.
    """
    def _ensure_data_dir(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    def _load_sessions(self) -> dict[str, Any]:
        self._ensure_data_dir()
        if not os.path.exists(SESSION_FILE):
            return {}
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_sessions(self, data: dict[str, Any]):
        self._ensure_data_dir()
        temp_file = f"{SESSION_FILE}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, SESSION_FILE)
        except Exception as e:
            print(f"❌ Error guardando sesión en JSON: {e}")

    def get_context(self, chat_id: int) -> str:
        data = self._load_sessions()
        history = data.get(str(chat_id), [])
        return self._format_context(history)

    def save_interaction(self, chat_id: int, user_msg: str, ai_msg: str):
        data = self._load_sessions()
        chat_key = str(chat_id)
        if chat_key not in data:
            data[chat_key] = []
        
        data[chat_key].append({"user": user_msg, "ai": ai_msg})
        
        if len(data[chat_key]) > MAX_HISTORY:
            data[chat_key] = data[chat_key][-MAX_HISTORY:]
        
        self._save_sessions(data)

    def _format_context(self, history: list[dict[str, str]]) -> str:
        if not history:
            return ""
        context_str = "\n--- 📜 CONTEXTO DE LA CONVERSACIÓN PREVIA ---\n"
        for item in history:
            context_str += f"User: {item.get('user', '')}\n"
            context_str += f"AI: {item.get('ai', '')}\n"
        context_str += "--- FIN DEL CONTEXTO ---\n"
        return context_str

# --- Firestore Session Manager (Production) ---
class FirestoreSessionManager(BaseSessionManager):
    """
    Gestor de persistencia usando Google Cloud Firestore.
    """
    def __init__(self, firestore_client):
        if firestore_client is None:
            raise ValueError("El cliente de Firestore no está inicializado.")
        self.db = firestore_client
        self.collection_ref = self.db.collection('sessions')

    def get_context(self, chat_id: int) -> str:
        doc_ref = self.collection_ref.document(str(chat_id))
        doc = doc_ref.get()
        if not doc.exists:
            return ""
        
        data = doc.to_dict()
        history = data.get('history', [])
        return self._format_context(history)

    def save_interaction(self, chat_id: int, user_msg: str, ai_msg: str):
        doc_ref = self.collection_ref.document(str(chat_id))
        doc = doc_ref.get()
        
        history = []
        if doc.exists:
            history = doc.to_dict().get('history', [])

        history.append({"user": user_msg, "ai": ai_msg})
        
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        
        try:
            doc_ref.set({'history': history}, merge=True)
        except Exception as e:
            print(f"❌ Error guardando sesión en Firestore: {e}")

    def _format_context(self, history: list[dict[str, str]]) -> str:
        if not history:
            return ""
        context_str = "\n--- 📜 CONTEXTO DE LA CONVERSACIÓN PREVIA ---\n"
        for item in history:
            context_str += f"User: {item.get('user', '')}\n"
            context_str += f"AI: {item.get('ai', '')}\n"
        context_str += "--- FIN DEL CONTEXTO ---\n"
        return context_str

# --- Factory Function ---
def SessionManager() -> BaseSessionManager:
    """
    Factory que devuelve la implementación del gestor de sesión
    basado en la variable de entorno USE_FIRESTORE.
    """
    if USE_FIRESTORE:
        if db:
            print("🚀 Usando Firestore para la gestión de sesiones.")
            return FirestoreSessionManager(firestore_client=db)
        else:
            print("⚠️  Firestore está habilitado (USE_FIRESTORE=True) pero falló la inicialización.")
            print("Fallback a JSON. La persistencia no funcionará en un entorno sin estado.")
            return JSONSessionManager()
    else:
        print("💾 Usando JSON local para la gestión de sesiones.")
        return JSONSessionManager()