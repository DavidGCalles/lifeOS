import os
from typing import Any
from google.cloud import firestore
from google.cloud.firestore import AsyncClient, Query 
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class SessionManager:
    """
    Gestor de sesiones en Firestore (Async Edition).
    Estructura: sessions/{chat_id}/messages/{message_id}
    """
    _firestore_client: AsyncClient | None = None
    _USE_FIRESTORE: bool = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
    _DB_NAME: str | None = os.getenv('FIRESTORE_DB_NAME')

    @classmethod
    def _get_db(cls) -> AsyncClient | None:
        """Inicialización Lazy del cliente Firestore Asíncrono."""
        if cls._firestore_client is None and cls._USE_FIRESTORE:
            try:
                # Instanciamos AsyncClient
                if cls._DB_NAME:
                    cls._firestore_client = AsyncClient(database=cls._DB_NAME)
                else:
                    cls._firestore_client = AsyncClient()
            except Exception as e:
                logger.error(f"❌ SESSION ERROR: No se pudo conectar a Firestore (Async): {e}")
                cls._firestore_client = None
        return cls._firestore_client

    @classmethod
    async def add_message(cls, chat_id: int | str, message_data: dict[str, Any]) -> None:
        """
        Guarda un mensaje de forma ASÍNCRONA.
        """
        db = cls._get_db()
        if not db:
            return

        cid = str(chat_id)
        
        # 1. Actualizar metadatos de la sesión padre (Upsert)
        session_ref = db.collection('sessions').document(cid)
        
        # Await obligatorio en operaciones de red
        await session_ref.set({
            'last_activity': firestore.SERVER_TIMESTAMP,
            'type': 'group' if cid.startswith('-') else 'private' 
        }, merge=True)

        # 2. Preparar payload
        msg_id_raw = message_data.get('message_id', '')
        msg_id_str = str(msg_id_raw)
        
        doc_data = {
            'message_id': msg_id_raw,
            'role': message_data.get('role', 'unknown'),
            'content': message_data.get('content', ''),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'sender_id': str(message_data.get('user_id', '')),
            'name': message_data.get('name', 'Unknown'),
            'input_type': message_data.get('input_type', 'text'),
            'agent_key': message_data.get('agent_key', None) 
        }

        try:
            # Operaciones awaitables
            if msg_id_str:
                await session_ref.collection('messages').document(msg_id_str).set(doc_data)
            else:
                await session_ref.collection('messages').add(doc_data)
        except Exception as e:
            logger.warning(f"⚠️ Error guardando mensaje en Firestore: {e}")

    @classmethod
    async def get_context(cls, chat_id: int | str, limit: int = 15) -> list[dict[str, Any]]:
        """
        Recupera historial reciente (Async).
        """
        db = cls._get_db()
        if not db:
            return []

        cid = str(chat_id)
        messages: list[dict[str, Any]] = []

        try:
            # Query definition is synchronous logic
            messages_ref = (
                db.collection('sessions')
                .document(cid)
                .collection('messages')
                .order_by('timestamp', direction=Query.DESCENDING)
                .limit(limit)
            )

            # Execution is async via stream()
            async for doc in messages_ref.stream():
                data = doc.to_dict()
                messages.append({
                    "message_id": data.get("message_id"),
                    "role": data.get("role"),
                    "name": data.get("name"),
                    "content": data.get("content")
                })
            
            return messages[::-1]

        except Exception as e:
            logger.warning(f"⚠️ Error recuperando contexto: {e}")
            return []

    @classmethod
    async def get_message_metadata(cls, chat_id: int | str, message_id: int | str) -> dict[str, Any] | None:
        """
        Retrieves metadata for a specific message to support Reply-To routing.
        Useful to check if a message was sent by a specific Agent.
        """
        db = cls._get_db()
        if not db:
            return None

        try:
            doc_ref = db.collection('sessions').document(str(chat_id)).collection('messages').document(str(message_id))
            doc = await doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.warning(f"⚠️ Error retrieving message metadata for {message_id}: {e}")
            return None