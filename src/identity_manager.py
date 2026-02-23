import json
import os
import logging

# FIX: Set gRPC environment variable to prevent noisy shutdown errors with uvloop.
# This must be set before any grpc-related libraries (like firestore) are imported.
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

from pathlib import Path
from enum import StrEnum, auto
from pydantic import BaseModel
from dotenv import load_dotenv
from google.cloud.firestore import AsyncClient
from google.cloud import firestore # Necesario para SERVER_TIMESTAMP

load_dotenv()

from src.logging_config import configure_logging
configure_logging(level=os.getenv('LOGGING_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

class UserRole(StrEnum):
    ADMIN = auto()      # Soberano
    FAMILY = auto()     # Círculo de confianza
    EXTERNAL = auto()   # Acceso limitado (Recruiters, APIs)
    PENDING = auto()    # Estado por defecto para desconocidos (Purgatorio)
    BLOCKED = auto()    # Lista negra (Ignorado)
    GUEST = auto()      # Legacy

class UserContext(BaseModel):
    telegram_id: str
    name: str
    role: UserRole
    description: str | None = None
    calendar_id: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

class IdentityManager:
    _users_db: dict[str, dict] = {}
    _loaded_local: bool = False
    
    _USE_FIRESTORE = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
    _DB_NAME = os.getenv('FIRESTORE_DB_NAME')
    _CONFIG_PATH: Path = Path(__file__).parent / "config" / "users.json"

    @classmethod
    def _get_firestore_client(cls) -> AsyncClient | None:
        # FIX: No caching. Always create a new client.
        # This solves the "different loop" issue when tools use asyncio.run().
        if cls._USE_FIRESTORE:
            try:
                if cls._DB_NAME:
                    return AsyncClient(database=cls._DB_NAME)
                else:
                    return AsyncClient()
            except Exception as e:
                logger.error(f"❌ Error connecting to Firestore (Async): {e}")
        return None

    @classmethod
    def _load_local_users(cls) -> None:
        if cls._loaded_local: return
        if not cls._CONFIG_PATH.exists():
            return
        try:
            with open(cls._CONFIG_PATH, "r", encoding="utf-8") as f:
                cls._users_db = json.load(f)
            cls._loaded_local = True
        except Exception as e:
            logger.error(f"❌ Local JSON error: {e}")

    @classmethod
    async def get_user(cls, telegram_id: int | str) -> UserContext:
        tid_str = str(telegram_id)
        logger.debug("🔍 User lookup initiated: telegram_id=%s", tid_str)
        
        # 0. PASE VIP DE EMERGENCIA
        env_admin_id = os.getenv("ADMIN_USER_ID")
        if env_admin_id and tid_str == str(env_admin_id):
            logger.info("🆔 Emergency ADMIN access granted via environment variable for user %s", tid_str)
            return UserContext(
                telegram_id=tid_str,
                name="Admin (Rescue)",
                role=UserRole.ADMIN,
                description="Emergency Access via Environment Variable"
            )

        # 1. INTENTO FIRESTORE (ASYNC)
        if cls._USE_FIRESTORE:
            logger.debug("📡 Attempting Firestore lookup for user %s", tid_str)
            db = cls._get_firestore_client()
            if db:
                try:
                    doc = await db.collection('users').document(tid_str).get()
                    if doc.exists:
                        data = doc.to_dict()
                        # Si el campo role no existe o es antiguo, fallback seguro a PENDING
                        role_str = data.get("role", "pending").lower()
                        user_ctx = UserContext(
                            telegram_id=tid_str,
                            name=data.get("name", "Unknown"),
                            role=UserRole(role_str), 
                            description=data.get("description"),
                            calendar_id=data.get("calendar_id")
                        )
                        logger.info("✅ User loaded from Firestore: id=%s name=%s role=%s", tid_str, user_ctx.name, user_ctx.role)
                        return user_ctx
                    else:
                        logger.debug("📭 User not found in Firestore: %s", tid_str)
                except Exception as e:
                    logger.warning("⚠️ Firestore lookup error for %s: %s", tid_str, str(e))

        # 2. FALLBACK LOCAL
        logger.debug("📂 Attempting local JSON lookup for user %s", tid_str)
        cls._load_local_users()
        data = cls._users_db.get(tid_str)
        if data:
            user_ctx = UserContext(
                telegram_id=tid_str,
                name=data.get("name"),
                role=UserRole(data.get("role", "guest").lower()),
                description=data.get("description"),
                calendar_id=data.get("calendar_id")
            )
            logger.info("✅ User loaded from local config: id=%s name=%s role=%s", tid_str, user_ctx.name, user_ctx.role)
            return user_ctx

        # 3. STRANGER -> PENDING (En lugar de Guest)
        # Devolvemos un contexto PENDING para que el sistema decida qué hacer (bloquear o notificar)
        logger.warning("⚠️ User not found in any database: telegram_id=%s, assigning PENDING role", tid_str)
        return UserContext(
            telegram_id=tid_str,
            name="Stranger",
            role=UserRole.PENDING,
            description="Unauthorized"
        )

    @classmethod
    async def register_user(cls, user: UserContext) -> bool:
        """
        Registra un usuario nuevo en Firestore usando estrictamente el modelo UserContext.
        """
        if not cls._USE_FIRESTORE:
            logger.warning("⚠️ Firestore not enabled; user registration skipped for %s", user.telegram_id)
            return False
        
        db = cls._get_firestore_client()
        if not db:
            logger.error("❌ Firestore client unavailable; cannot register user %s", user.telegram_id)
            return False

        try:
            # Serialización estricta del modelo Pydantic
            # Excluimos telegram_id del body porque ya es la Key del documento
            user_data = user.model_dump(exclude={'telegram_id'})
            
            # Solo añadimos metadata de sistema necesaria para ordenación
            user_data['first_seen'] = firestore.SERVER_TIMESTAMP
            
            logger.info("📝 Registering user: id=%s name=%s role=%s", user.telegram_id, user.name, user.role)

            await db.collection('users').document(user.telegram_id).set(user_data, merge=True)
            logger.info("✅ User registered successfully: id=%s", user.telegram_id)
            return True
        except Exception as e:
            logger.error("❌ Error registering user %s: %s", user.telegram_id, str(e), exc_info=True)
            return False

    @classmethod
    async def update_user(cls, telegram_id: int | str, data: dict) -> bool:
        tid_str = str(telegram_id)
        
        logger.debug("🔄 User update initiated: telegram_id=%s fields=%s", tid_str, list(data.keys()))
        
        if not cls._USE_FIRESTORE:
            logger.warning("⚠️ Firestore not enabled; user update skipped for %s", tid_str)
            return False

        db = cls._get_firestore_client()
        if not db:
            logger.error("❌ Firestore client unavailable; cannot update user %s", tid_str)
            return False

        try:
            logger.info("💾 Updating user %s with fields: %s", tid_str, list(data.keys()))
            await db.collection('users').document(tid_str).set(data, merge=True)
            logger.info("✅ User updated successfully: id=%s", tid_str)
            return True
        except Exception as e:
            logger.error("❌ Error updating user %s: %s", tid_str, str(e), exc_info=True)
            return False

    @classmethod
    async def get_user_by_name(cls, name: str) -> UserContext | None:
        """
        Intenta encontrar un UserContext por nombre. Prioriza Firestore.
        """
        logger.debug("🔍 User lookup by name: name='%s'", name)
        
        # Normalizar nombre para búsqueda case-insensitive
        normalized_name = name.strip().lower()

        if cls._USE_FIRESTORE:
            db = cls._get_firestore_client()
            if db:
                try:
                    # Realiza una query para buscar por el campo 'name'
                    # Firestore requiere índices para queries de rango/ordenación o igualdad en campos no ID.
                    # Asumimos que 'name' no es un campo muy grande y que los nombres serán únicos
                    # o que aceptamos el primer match.
                    users_ref = db.collection('users').where('name', '==', name).limit(1)
                    async for doc in users_ref.stream():
                        data = doc.to_dict()
                        role_str = data.get("role", "pending").lower()
                        return UserContext(
                            telegram_id=doc.id,  # El ID del documento es el telegram_id
                            name=data.get("name", "Unknown"),
                            role=UserRole(role_str),
                            description=data.get("description"),
                            calendar_id=data.get("calendar_id")
                        )
                except Exception as e:
                    logger.error(f"⚠️ Fallo búsqueda por nombre en Firestore: {e}")

        # Fallback a búsqueda local (si aplica)
        cls._load_local_users()
        for tid, data in cls._users_db.items():
            if data.get('name', '').lower() == normalized_name:
                return UserContext(
                    telegram_id=tid,
                    name=data.get("name"),
                    role=UserRole(data.get("role", "guest").lower()),
                    description=data.get("description"),
                    calendar_id=data.get("calendar_id")
                )
        
        logger.info(f"IdentityManager: No user found for name '{name}'")
        return None

    @classmethod
    async def get_user_by_email(cls, email: str) -> UserContext | None:
        """
        Search for a user by their calendar_id (email).
        """
        normalized_email = email.strip().lower()
        logger.debug(f"IdentityManager: Looking up user by email '{normalized_email}'")

        if cls._USE_FIRESTORE:
            db = cls._get_firestore_client()
            if db:
                try:
                    users_ref = db.collection('users').where('calendar_id', '==', normalized_email).limit(1)
                    async for doc in users_ref.stream():
                        data = doc.to_dict()
                        role_str = data.get("role", "pending").lower()
                        logger.info(f"IdentityManager: Found user by email: {normalized_email}")
                        return UserContext(
                            telegram_id=doc.id,
                            name=data.get("name", "Unknown"),
                            role=UserRole(role_str),
                            description=data.get("description"),
                            calendar_id=data.get("calendar_id")
                        )
                except Exception as e:
                    logger.error(f"⚠️ Error searching Firestore by email: {e}")

        # Fallback to local search
        cls._load_local_users()
        for tid, data in cls._users_db.items():
            if data.get('calendar_id', '').lower() == normalized_email:
                logger.info(f"IdentityManager: Found user by email (local): {normalized_email}")
                return UserContext(
                    telegram_id=tid,
                    name=data.get("name"),
                    role=UserRole(data.get("role", "guest").lower()),
                    description=data.get("description"),
                    calendar_id=data.get("calendar_id")
                )
        
        logger.info(f"IdentityManager: No user found for email '{normalized_email}'")
        return None