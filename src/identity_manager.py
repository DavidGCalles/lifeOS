import json
import os
from pathlib import Path
from enum import StrEnum, auto
from pydantic import BaseModel
from dotenv import load_dotenv

# Cargamos entorno para asegurar que USE_FIRESTORE está disponible
load_dotenv()

# --- DEFINICIONES DE DOMINIO ---

class UserRole(StrEnum):
    ADMIN = auto()  # "admin"
    USER = auto()   # "user"
    GUEST = auto()  # "guest"

class UserContext(BaseModel):
    """
    Representa al usuario activo en la sesión actual.
    """
    telegram_id: str
    name: str
    role: UserRole
    description: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

# --- MANAGER ---

class IdentityManager:
    """
    Gestor de identidad híbrido (Firestore + Local JSON Fallback).
    """
    _users_db: dict[str, dict] = {}
    _loaded_local: bool = False
    _firestore_client = None
    
    # Configuración
    _USE_FIRESTORE = os.getenv('USE_FIRESTORE', 'False').lower() == 'true'
    _DB_NAME = os.getenv('FIRESTORE_DB_NAME')
    _CONFIG_PATH: Path = Path(__file__).parent / "config" / "users.json"

    @classmethod
    def _get_firestore_client(cls):
        """Inicialización Lazy del cliente conectando a la DB específica."""
        if cls._firestore_client is None and cls._USE_FIRESTORE:
            try:
                from google.cloud import firestore
                
                # Si hay nombre de DB, lo usamos. Si es None, usa '(default)'
                if cls._DB_NAME:
                    print(f"🔥 IDENTITY: Conectando a base de datos: '{cls._DB_NAME}'...")
                    cls._firestore_client = firestore.Client(database=cls._DB_NAME)
                else:
                    print("🔥 IDENTITY: Conectando a base de datos: (default)...")
                    cls._firestore_client = firestore.Client()
                    
                print("✅ IDENTITY: Cliente Firestore inicializado.")
            except ImportError:
                print("❌ ERROR: google-cloud-firestore no instalado.")
            except Exception as e:
                print(f"❌ IDENTITY ERROR: Fallo al conectar con Firestore: {e}")
                cls._firestore_client = None
        return cls._firestore_client

    @classmethod
    def _load_local_users(cls) -> None:
        """Carga el JSON local (Plan B)."""
        if cls._loaded_local:
            return

        if not cls._CONFIG_PATH.exists():
            # Si no hay JSON y falló Firestore, estamos ciegos, pero no rompemos.
            return

        try:
            with open(cls._CONFIG_PATH, "r", encoding="utf-8") as f:
                cls._users_db = json.load(f)
            cls._loaded_local = True
            print("📂 IDENTITY: Base de datos local (JSON) cargada.")
        except Exception as e:
            print(f"❌ IDENTITY ERROR: JSON corrupto: {e}")
            cls._users_db = {}

    @classmethod
    def get_user(cls, telegram_id: int | str) -> UserContext:
        """
        Recupera el perfil del usuario.
        Estrategia: Firestore (si activo) -> JSON Local -> Stranger (Guest).
        """
        tid_str = str(telegram_id)
        user_data = None
        source = "Unknown"

        # 1. INTENTO FIRESTORE (Producción)
        if cls._USE_FIRESTORE:
            db = cls._get_firestore_client()
            if db:
                try:
                    # Buscamos en colección 'users', documento = telegram_id
                    doc = db.collection('users').document(tid_str).get()
                    if doc.exists:
                        user_data = doc.to_dict()
                        source = "Firestore"
                except Exception as e:
                    print(f"⚠️ IDENTITY WARNING: Fallo de lectura en nube para {tid_str}: {e}")

        # 2. INTENTO JSON LOCAL (Desarrollo / Fallback)
        if not user_data:
            cls._load_local_users()
            user_data = cls._users_db.get(tid_str)
            if user_data:
                source = "Local JSON"

        # 3. RESOLUCIÓN DE IDENTIDAD
        if user_data:
            # Normalización de datos para evitar errores si falta algún campo en BBDD
            role_str = user_data.get("role", "guest").lower()
            # Mapeo seguro a Enum (si hay basura en la DB, degradamos a GUEST)
            try:
                role_enum = UserRole(role_str)
            except ValueError:
                role_enum = UserRole.GUEST

            print(f"👤 USER RECOGNIZED [{source}]: {user_data.get('name')} ({role_enum})")
            
            return UserContext(
                telegram_id=tid_str,
                name=user_data.get("name", "Usuario"),
                role=role_enum,
                description=user_data.get("description", "")
            )

        # 4. DESCONOCIDO (GUEST por defecto)
        print(f"👤 USER UNKNOWN: ID {tid_str}")
        return UserContext(
            telegram_id=tid_str,
            name="Stranger",
            role=UserRole.GUEST,
            description="Unauthorized user seeking access."
        )

    @classmethod
    def reload(cls) -> None:
        """Útil para debug en local sin reiniciar."""
        cls._loaded_local = False
        cls._load_local_users()