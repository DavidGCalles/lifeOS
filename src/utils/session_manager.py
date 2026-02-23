import os
from typing import Any
from google.cloud import firestore
from google.cloud.firestore import AsyncClient, Query 
from dotenv import load_dotenv
import logging
from pydantic import ValidationError

# import the new schemas needed for validation
from src.schemas.memory import (
    SessionMessage,
    BaseMemoryMetadata,
    MemoryVisibility,
    MemoryDomainType,
)

load_dotenv()
logger = logging.getLogger(__name__)

class SessionManager:
    """
    Gestor de sesiones en Firestore (Async Edition).
    Estructura: sessions/{chat_id}/messages/{message_id}

    **Schema enforcement:** every document written by `add_message` is
    validated against the `SessionMessage` Pydantic model (see
    `src.schemas.memory`). This guarantees that the universal RBAC fields
    (`owner_id`, `visibility`, `domain`) are always present, preventing
    arbitrary dictionaries from bypassing access control.

    New conversational turns default to `PRIVATE` visibility and
    `owner_id` is derived automatically from the Telegram user ID.
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
    async def add_message(cls, chat_id: int | str, message_data: dict[str, Any]):
        """
        Guarda un mensaje de forma ASÍNCRONA, validándolo primero contra SessionMessage.
        Devuelve el objeto SessionMessage validado.
        """
        db = cls._get_db()
        cid = str(chat_id)
        
        # 1. Extraer identificadores base
        owner_id = str(message_data.get('user_id', message_data.get('sender_id', 'unknown')))
        
        # 2. Construir payload base con defaults solo para lo NO crítico
        session_payload = {
            "sender_id": owner_id,
            "name": message_data.get('name', 'Unknown'),
            "input_type": message_data.get('input_type', 'text'),
            "metadata": {
                "owner_id": owner_id,
                "visibility": message_data.get('visibility', 'PRIVATE'),
                "domain": "episodic" 
            }
        }

        # 3. Mapear campos críticos SIN defaults (para que Pydantic chille si faltan)
        if 'role' in message_data: session_payload['role'] = message_data['role']
        if 'content' in message_data: session_payload['content'] = message_data['content']
        
        # Opcionales
        if 'message_id' in message_data: session_payload['message_id'] = message_data['message_id']
        if 'agent_key' in message_data: session_payload['agent_key'] = message_data['agent_key']

        # 4. Validación Estricta
        # Aquí es donde tu test lanzará el ValidationError si faltan role o content
        validated_msg = SessionMessage(**session_payload)

        # 5. Persistencia en Firestore
        if db:
            session_ref = db.collection('sessions').document(cid)
            
            await session_ref.set({
                'last_activity': firestore.SERVER_TIMESTAMP,
                'type': 'group' if cid.startswith('-') else 'private' 
            }, merge=True)

            doc_data = validated_msg.model_dump(exclude_none=True)
            doc_data['timestamp'] = firestore.SERVER_TIMESTAMP

            msg_id_raw = validated_msg.message_id
            msg_id_str = str(msg_id_raw) if msg_id_raw else None

            try:
                if msg_id_str:
                    await session_ref.collection('messages').document(msg_id_str).set(doc_data)
                else:
                    await session_ref.collection('messages').add(doc_data)
            except Exception as e:
                logger.warning(f"⚠️ Error guardando mensaje en Firestore: {e}")

        return validated_msg

    @classmethod
    def build_log_content(cls, sensory_payload: dict | None, sanitized_input: str | None, message) -> tuple[str, str]:
        """
        Utility to produce a lightweight log content and input_type from either a sensory payload
        or plain message text / sanitized_input. Returns (log_content, input_type).

        This is intentionally simple and only prepares strings for Firestore writes — no analysis
        or vectorization is performed here.
        """
        # Default
        input_type = 'text'
        log_content = ''

        if sensory_payload:
            content = sensory_payload.get('content', '')
            metadata = sensory_payload.get('metadata', {}) or {}
            input_type = metadata.get('input_type', 'multimodal' if isinstance(content, list) else 'text')

            if isinstance(content, list):
                text_part = next((str(x.get('text', '')) for x in content if x.get('type') == 'text'), '')
                if text_part:
                    log_content = f"[{input_type.upper()} FILE] {text_part}"
                else:
                    log_content = f"[{input_type.upper()} FILE]"
            else:
                log_content = str(content)
        else:
            log_content = sanitized_input if sanitized_input is not None else (getattr(message, 'text', '') or '')
            input_type = 'text'

        return log_content, input_type

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
                    "content": data.get("content"),
                    # propagate RBAC metadata if present so callers can make
                    # trust decisions or display ownership info.
                    "metadata": {
                        "owner_id": data.get("owner_id"),
                        "visibility": data.get("visibility"),
                        "domain": data.get("domain"),
                    }
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