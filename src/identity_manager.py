import json
import os
import logging
from pathlib import Path
from enum import StrEnum, auto
from pydantic import BaseModel
from dotenv import load_dotenv
from google.cloud.firestore import AsyncClient
from google.cloud import firestore # Necesario para SERVER_TIMESTAMP

load_dotenv()

logging.basicConfig(level=os.getenv('LOGGING_LEVEL', 'INFO').upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    _firestore_client: AsyncClient | None = None
    
    _USE_FIRESTORE = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
    _DB_NAME = os.getenv('FIRESTORE_DB_NAME')
    _CONFIG_PATH: Path = Path(__file__).parent / "config" / "users.json"

    @classmethod
    def _get_firestore_client(cls) -> AsyncClient | None:
        if cls._firestore_client is None and cls._USE_FIRESTORE:
            try:
                if cls._DB_NAME:
                    cls._firestore_client = AsyncClient(database=cls._DB_NAME)
                else:
                    cls._firestore_client = AsyncClient()
            except Exception as e:
                logger.error(f"❌ Error conectando a Firestore (Async): {e}")
                cls._firestore_client = None
        return cls._firestore_client

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
        
        # 0. PASE VIP DE EMERGENCIA
        env_admin_id = os.getenv("ADMIN_USER_ID")
        if env_admin_id and tid_str == str(env_admin_id):
            pass 

        # 1. INTENTO FIRESTORE (ASYNC)
        if cls._USE_FIRESTORE:
            db = cls._get_firestore_client()
            if db:
                try:
                    doc = await db.collection('users').document(tid_str).get()
                    if doc.exists:
                        data = doc.to_dict()
                        # Si el campo role no existe o es antiguo, fallback seguro a PENDING
                        role_str = data.get("role", "pending").lower()
                        return UserContext(
                            telegram_id=tid_str,
                            name=data.get("name", "Unknown"),
                            role=UserRole(role_str), 
                            description=data.get("description"),
                            calendar_id=data.get("calendar_id")
                        )
                except Exception as e:
                    logger.error(f"⚠️ Fallo lectura Firestore: {e}")

        # 2. FALLBACK LOCAL / VIP MANUAL
        if env_admin_id and tid_str == str(env_admin_id):
             return UserContext(
                telegram_id=tid_str,
                name="Admin (Rescue)",
                role=UserRole.ADMIN,
                description="Emergency Access via Environment Variable"
            )

        cls._load_local_users()
        data = cls._users_db.get(tid_str)
        if data:
            return UserContext(
                telegram_id=tid_str,
                name=data.get("name"),
                role=UserRole(data.get("role", "guest").lower()),
                description=data.get("description"),
                calendar_id=data.get("calendar_id")
            )

        # 3. STRANGER -> PENDING (En lugar de Guest)
        # Devolvemos un contexto PENDING para que el sistema decida qué hacer (bloquear o notificar)
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
        if not cls._USE_FIRESTORE: return False
        
        db = cls._get_firestore_client()
        if not db: return False

        try:
            # Serialización estricta del modelo Pydantic
            # Excluimos telegram_id del body porque ya es la Key del documento
            user_data = user.model_dump(exclude={'telegram_id'})
            
            # Solo añadimos metadata de sistema necesaria para ordenación
            user_data['first_seen'] = firestore.SERVER_TIMESTAMP

            await db.collection('users').document(user.telegram_id).set(user_data, merge=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error registering user: {e}")
            return False

    @classmethod
    async def update_user(cls, telegram_id: int | str, data: dict) -> bool:
        tid_str = str(telegram_id)
        
        if not cls._USE_FIRESTORE:
            return False

        db = cls._get_firestore_client()
        if not db: return False

        try:
            logger.info(f"💾 Actualizando usuario {tid_str} con: {data}")
            await db.collection('users').document(tid_str).set(data, merge=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error escribiendo en Firestore: {e}")
            return False