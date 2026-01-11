import os
from typing import Any
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

class SessionManager:
    """
    Gestor de sesiones en Firestore (Python 3.12+).
    Estructura: sessions/{chat_id}/messages/{message_id}
    """
    _firestore_client: firestore.Client | None = None
    _USE_FIRESTORE: bool = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
    _DB_NAME: str | None = os.getenv('FIRESTORE_DB_NAME')

    @classmethod
    def _get_db(cls) -> firestore.Client | None:
        """Inicialización Lazy del cliente Firestore."""
        if cls._firestore_client is None and cls._USE_FIRESTORE:
            try:
                # Soporte para bases de datos nombradas (no default)
                if cls._DB_NAME:
                    cls._firestore_client = firestore.Client(database=cls._DB_NAME)
                else:
                    cls._firestore_client = firestore.Client()
            except Exception as e:
                print(f"❌ SESSION ERROR: No se pudo conectar a Firestore: {e}")
                cls._firestore_client = None
        return cls._firestore_client

    @classmethod
    def add_message(cls, chat_id: int | str, message_data: dict[str, Any]) -> None:
        """
        Guarda un mensaje en la subcolección 'messages'.
        
        Args:
            chat_id: ID del chat (positivo=privado, negativo=grupo).
            message_data: Diccionario con 'role', 'content', 'user_id', 'name', 'message_id'.
        """
        db = cls._get_db()
        if not db:
            return

        cid = str(chat_id)
        
        # 1. Actualizar metadatos de la sesión padre (Upsert)
        # Se asume que 'sessions' es la colección raíz
        session_ref = db.collection('sessions').document(cid)
        session_ref.set({
            'last_activity': firestore.SERVER_TIMESTAMP,
            'type': 'group' if cid.startswith('-') else 'private' 
        }, merge=True)

        # 2. Preparar el payload del mensaje
        # Convertimos message_id a string para usarlo como ID de documento
        msg_id_raw = message_data.get('message_id', '')
        msg_id_str = str(msg_id_raw)
        
        doc_data = {
            'message_id': msg_id_raw,  # Guardamos el valor original (int o str)
            'role': message_data.get('role', 'unknown'),
            'content': message_data.get('content', ''),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'sender_id': str(message_data.get('user_id', '')),
            'name': message_data.get('name', 'Unknown')
        }

        try:
            # Usamos el ID de Telegram como ID del documento para idempotencia
            if msg_id_str:
                session_ref.collection('messages').document(msg_id_str).set(doc_data)
            else:
                # Fallback seguro si no hay ID (no debería ocurrir en Telegram)
                session_ref.collection('messages').add(doc_data)
        except Exception as e:
            print(f"⚠️ Error guardando mensaje en Firestore: {e}")

    @classmethod
    def get_context(cls, chat_id: int | str, limit: int = 15) -> list[dict[str, Any]]:
        """
        Recupera el historial reciente formateado para el LLM.
        Devuelve lista en orden cronológico (Oldest -> Newest).
        """
        db = cls._get_db()
        if not db:
            return []

        cid = str(chat_id)
        messages: list[dict[str, Any]] = []

        try:
            # Consulta: Los N más recientes (orden Descendente por tiempo)
            docs = (
                db.collection('sessions')
                .document(cid)
                .collection('messages')
                .order_by('timestamp', direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )

            # Iteramos y formateamos
            for doc in docs:
                data = doc.to_dict()
                messages.append({
                    "message_id": data.get("message_id"),
                    "role": data.get("role"),
                    "name": data.get("name"),
                    "content": data.get("content")
                })
            
            # Invertimos la lista para que el LLM lea la conversación en orden natural
            return messages[::-1]

        except Exception as e:
            print(f"⚠️ Error recuperando contexto: {e}")
            return []