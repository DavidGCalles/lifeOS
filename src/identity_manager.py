import json
import os
import logging
from pathlib import Path
from enum import StrEnum, auto
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=os.getenv('LOGGING_LEVEL', 'INFO').upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UserRole(StrEnum):
    ADMIN = auto()
    USER = auto()
    GUEST = auto()

class UserContext(BaseModel):
    telegram_id: str
    name: str
    role: UserRole
    description: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

class IdentityManager:
    _users_db: dict[str, dict] = {}
    _loaded_local: bool = False
    _firestore_client = None
    
    _USE_FIRESTORE = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
    _DB_NAME = os.getenv('FIRESTORE_DB_NAME')
    # Intenta buscar en varios sitios por si acaso
    _CONFIG_PATH: Path = Path(__file__).parent / "config" / "users.json"

    @classmethod
    def _get_firestore_client(cls):
        if cls._firestore_client is None and cls._USE_FIRESTORE:
            try:
                from google.cloud import firestore
                if cls._DB_NAME:
                    cls._firestore_client = firestore.Client(database=cls._DB_NAME)
                else:
                    cls._firestore_client = firestore.Client()
            except Exception as e:
                logger.error(f"❌ Error conectando a Firestore: {e}")
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
    def get_user(cls, telegram_id: int | str) -> UserContext:
        tid_str = str(telegram_id)
        
        # --- 0. PASE VIP DE EMERGENCIA (ENV VAR) ---
        # Esto te salva si no hay JSON ni Firestore
        env_admin_id = os.getenv("ADMIN_USER_ID")
        if env_admin_id and tid_str == str(env_admin_id):
            logger.info(f"🛡️ ACCESO DE RESCATE (Env Var) para: {tid_str}")
            return UserContext(
                telegram_id=tid_str,
                name="Admin (Rescue)",
                role=UserRole.ADMIN,
                description="Emergency Access via Environment Variable"
            )
        # -------------------------------------------

        # 1. INTENTO FIRESTORE
        if cls._USE_FIRESTORE:
            db = cls._get_firestore_client()
            if db:
                try:
                    doc = db.collection('users').document(tid_str).get()
                    if doc.exists:
                        data = doc.to_dict()
                        return UserContext(
                            telegram_id=tid_str,
                            name=data.get("name", "Usuario"),
                            role=UserRole(data.get("role", "guest").lower()),
                            description=data.get("description")
                        )
                except Exception as e:
                    logger.error(f"⚠️ Fallo lectura Firestore: {e}")

        # 2. FALLBACK LOCAL
        cls._load_local_users()
        data = cls._users_db.get(tid_str)
        if data:
            return UserContext(
                telegram_id=tid_str,
                name=data.get("name"),
                role=UserRole(data.get("role", "guest").lower()),
                description=data.get("description")
            )

        # 3. STRANGER
        logger.warning(f"⛔ Acceso denegado: {tid_str}")
        return UserContext(
            telegram_id=tid_str,
            name="Stranger",
            role=UserRole.GUEST,
            description="Unauthorized"
        )