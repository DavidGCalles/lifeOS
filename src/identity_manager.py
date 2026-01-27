import json
import os
import logging
from pathlib import Path
from enum import StrEnum, auto
from pydantic import BaseModel
from dotenv import load_dotenv
from google.cloud.firestore import AsyncClient # Import Async

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
    calendar_id: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

class IdentityManager:
    _users_db: dict[str, dict] = {}
    _loaded_local: bool = False
    _firestore_client: AsyncClient | None = None # Type checking
    
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
        # Esta carga de JSON local es muy rápida y se hace una vez,
        # podemos dejarla sincrona o envolverla si el archivo fuera enorme.
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
            # Nota: El usuario de rescate no suele tener persistencia, 
            # pero intentamos leer de firestore por si acaso tiene datos guardados.
            pass 

        # 1. INTENTO FIRESTORE (ASYNC)
        if cls._USE_FIRESTORE:
            db = cls._get_firestore_client()
            if db:
                try:
                    doc = await db.collection('users').document(tid_str).get()
                    if doc.exists:
                        data = doc.to_dict()
                        return UserContext(
                            telegram_id=tid_str,
                            name=data.get("name", "Usuario"),
                            role=UserRole(data.get("role", "guest").lower()),
                            description=data.get("description"),
                            calendar_id=data.get("calendar_id") # [ADR-010-002] Mapeo
                        )
                except Exception as e:
                    logger.error(f"⚠️ Fallo lectura Firestore: {e}")

        # 2. FALLBACK LOCAL / VIP MANUAL
        # Si falló firestore o no está activo, miramos si es el VIP de entorno
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

        # 3. STRANGER
        logger.warning(f"⛔ Acceso denegado: {tid_str}")
        return UserContext(
            telegram_id=tid_str,
            name="Stranger",
            role=UserRole.GUEST,
            description="Unauthorized"
        )

    # [ADR-010-002] NUEVO MÉTODO DE ESCRITURA
    @classmethod
    async def update_user(cls, telegram_id: int | str, data: dict) -> bool:
        """
        Actualiza parcialmente los datos del usuario en Firestore.
        Ejemplo: await IdentityManager.update_user(12345, {"calendar_id": "pepe@gmail.com"})
        """
        tid_str = str(telegram_id)
        
        if not cls._USE_FIRESTORE:
            logger.warning("⚠️ Intentando escribir en IdentityManager con FIRESTORE DESACTIVADO. Operación ignorada.")
            # Aquí podríamos implementar escritura en el JSON local si quisieras, 
            # pero por ahora el requisito es Firestore.
            return False

        db = cls._get_firestore_client()
        if not db:
            logger.error("❌ No hay conexión a DB para actualizar usuario.")
            return False

        try:
            logger.info(f"💾 Actualizando usuario {tid_str} con: {data}")
            # merge=True asegura que no borramos datos existentes (como el rol)
            await db.collection('users').document(tid_str).set(data, merge=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error escribiendo en Firestore: {e}")
            return False