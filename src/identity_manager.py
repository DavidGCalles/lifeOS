import json
import os
from pathlib import Path
from enum import StrEnum, auto
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# --- DEFINICIONES ---

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

# --- MANAGER ---

class IdentityManager:
    _users_db: dict[str, dict] = {}
    _loaded_local: bool = False
    _firestore_client = None
    
    # Configuración
    _USE_FIRESTORE = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
    _DB_NAME = os.getenv('FIRESTORE_DB_NAME')
    _CONFIG_PATH: Path = Path(__file__).parent / "config" / "users.json"

    @classmethod
    def _get_firestore_client(cls):
        """Inicializa con logs de diagnóstico."""
        if cls._firestore_client is None and cls._USE_FIRESTORE:
            try:
                from google.cloud import firestore
                
                print(f"🔧 DIAGNOSTICO FIRESTORE:")
                print(f"   - Variable USE_FIRESTORE: {cls._USE_FIRESTORE}")
                print(f"   - Variable FIRESTORE_DB_NAME: '{cls._DB_NAME}'")
                
                # Inicialización explícita
                if cls._DB_NAME:
                    cls._firestore_client = firestore.Client(database=cls._DB_NAME)
                else:
                    cls._firestore_client = firestore.Client()
                
                # Verificación post-conexión
                print(f"   - Cliente creado. Proyecto: {cls._firestore_client.project}")
                # Nota: ._database es interno, pero útil para debug
                try:
                    print(f"   - Target DB: {cls._firestore_client._database}")
                except:
                    pass
                    
            except Exception as e:
                print(f"❌ CRITICAL ERROR conectando a Firestore: {type(e).__name__}: {e}")
                cls._firestore_client = None
        return cls._firestore_client

    @classmethod
    def _load_local_users(cls) -> None:
        """Fallback local."""
        if cls._loaded_local: return
        if not cls._CONFIG_PATH.exists():
            print(f"⚠️ Local config not found: {cls._CONFIG_PATH}")
            return
        try:
            with open(cls._CONFIG_PATH, "r", encoding="utf-8") as f:
                cls._users_db = json.load(f)
            cls._loaded_local = True
        except Exception as e:
            print(f"❌ Local JSON error: {e}")

    @classmethod
    def get_user(cls, telegram_id: int | str) -> UserContext:
        tid_str = str(telegram_id)
        
        # 1. INTENTO FIRESTORE
        if cls._USE_FIRESTORE:
            db = cls._get_firestore_client()
            if db:
                try:
                    # Intento de lectura explícito
                    doc_ref = db.collection('users').document(tid_str)
                    print(f"🔍 Buscando en Firestore: {doc_ref.path} ...")
                    
                    doc = doc_ref.get()
                    
                    if doc.exists:
                        data = doc.to_dict()
                        print(f"✅ ENCONTRADO en Firestore: {data.get('name')}")
                        return UserContext(
                            telegram_id=tid_str,
                            name=data.get("name", "Usuario"),
                            role=UserRole(data.get("role", "guest").lower()),
                            description=data.get("description")
                        )
                    else:
                        print(f"🚫 NO EXISTE en Firestore el ID: {tid_str}")
                except Exception as e:
                    # Aquí está la clave: Ver el error real
                    print(f"❌ EXCEPCION LEYENDO USUARIO: {e}")

        # 2. FALLBACK LOCAL
        cls._load_local_users()
        data = cls._users_db.get(tid_str)
        if data:
            print(f"📂 Encontrado en Local JSON: {data.get('name')}")
            return UserContext(
                telegram_id=tid_str,
                name=data.get("name"),
                role=UserRole(data.get("role", "guest").lower()),
                description=data.get("description")
            )

        # 3. STRANGER
        print(f"⛔ Acceso denegado final para: {tid_str}")
        return UserContext(
            telegram_id=tid_str,
            name="Stranger",
            role=UserRole.GUEST,
            description="Unauthorized"
        )

    @classmethod
    def reload(cls):
        cls._loaded_local = False
        cls._load_local_users()