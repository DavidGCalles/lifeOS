import json
from pathlib import Path
from enum import StrEnum, auto
from pydantic import BaseModel

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

# --- MANAGER (SINGLETON) ---

class IdentityManager:
    _users_db: dict[str, dict] = {}
    _loaded: bool = False

    # Ruta relativa: src/identity_manager.py -> .../src/config/users.json
    _CONFIG_PATH: Path = Path(__file__).parent / "config" / "users.json"

    @classmethod
    def _load_users(cls) -> None:
        """Carga la configuración de usuarios si no está cargada."""
        if cls._loaded:
            return

        if not cls._CONFIG_PATH.exists():
            print(f"⚠️ IDENTITY WARNING: Config file not found at {cls._CONFIG_PATH}")
            cls._users_db = {}
            return

        try:
            with open(cls._CONFIG_PATH, "r", encoding="utf-8") as f:
                cls._users_db = json.load(f)
            cls._loaded = True
        except Exception as e:
            print(f"❌ IDENTITY ERROR: Failed to parse users.json: {e}")
            cls._users_db = {}

    @classmethod
    def get_user(cls, telegram_id: int | str) -> UserContext:
        """
        Resuelve la identidad basada en el ID de Telegram.
        """
        cls._load_users()
        
        # Normalizamos a string
        tid_str = str(telegram_id)
        
        user_data = cls._users_db.get(tid_str)

        if user_data:
            # Usuario Conocido (Whitelisted)
            # Mapeamos strings del JSON a Enums y Modelos
            return UserContext(
                telegram_id=tid_str,
                name=user_data.get("name", "Unknown"),
                role=UserRole(user_data.get("role", "user").lower()),
                description=user_data.get("description")
            )
        
        # Usuario Desconocido (Guest)
        return UserContext(
            telegram_id=tid_str,
            name="Stranger",
            role=UserRole.GUEST,
            description="Unauthorized user"
        )

    @classmethod
    def reload(cls) -> None:
        """Fuerza la recarga del JSON (Hot-Reload)."""
        cls._loaded = False
        cls._load_users()