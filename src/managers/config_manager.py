import os
import logging
from typing import Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Single Source of Truth for system configuration and credentials.
    Implements Profile-Driven Architecture based solely on the 'ENVIRONMENT' master variable.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.environment = os.getenv("ENVIRONMENT", "edge").lower()
        self.config: dict[str, Any] = {}
        
        logger.info(f"⚙️ Bootstrapping ConfigManager with profile: {self.environment}")
        self._resolve_profile()
        self._initialized = True

        # Initialize async database engine
        self._async_engine = create_async_engine(
            self.get_postgres_url(),
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
        )

    def _resolve_profile(self):
        """Resolves configuration based on the active environment profile."""
        if self.environment == "cloud":
            self._resolve_cloud_profile()
        elif self.environment == "edge":
            self._resolve_edge_profile()
        elif self.environment == "hybrid":
            self._resolve_hybrid_profile()
        else:
            logger.critical(f"❌ Invalid ENVIRONMENT value: '{self.environment}'. Must be 'cloud', 'edge', or 'hybrid'.")
            raise ValueError(f"Invalid ENVIRONMENT profile: {self.environment}")
            
        # Common configurations regardless of profile
        self.config["litellm_url"] = os.getenv("LITELLM_URL", "http://litellm:4000")
        if not self.config["litellm_url"].endswith("/v1"):
            self.config["litellm_url"] += "/v1"
            
        self.config["litellm_api_key"] = os.getenv("LITELLM_API_KEY", "sk-fake-key")
        self.config["embedding_api_base"] = os.getenv("EMBEDDING_API_BASE", "http://lifeos_embeddings:8080")

    def _resolve_cloud_profile(self):
        """
        Injects managed cloud credentials:
        - Supabase Cloud
        - Qdrant Cloud
        """
        logger.info("☁️ Resolving 'cloud' profile credentials...")
        
        qdrant_host = os.getenv("QDRANT_CLOUD_HOST")
        qdrant_api_key = os.getenv("QDRANT_CLOUD_API_KEY")
        postgres_url = os.getenv("SUPABASE_URL") or os.getenv("POSTGRES_CLOUD_URL")
        
        if not all([qdrant_host, qdrant_api_key, postgres_url]):
            logger.critical("❌ Missing credentials for 'cloud' profile. Ensure QDRANT_CLOUD_HOST, QDRANT_CLOUD_API_KEY, and SUPABASE_URL (or POSTGRES_CLOUD_URL) are set.")
            raise ValueError("Incomplete cloud profile configuration")
            
        self.config["qdrant_host"] = qdrant_host
        self.config["qdrant_api_key"] = qdrant_api_key
        self.config["postgres_url"] = self._ensure_asyncpg_url(postgres_url)

    def _resolve_edge_profile(self):
        """
        Injects local container credentials:
        - Local Postgres
        - Local Qdrant
        """
        logger.info("🔪 Resolving 'edge' profile credentials...")
        
        self.config["qdrant_host"] = os.getenv("QDRANT_LOCAL_HOST", "http://qdrant:6333")
        self.config["qdrant_api_key"] = None  # Local Qdrant doesn't need API key by default
        
        pg_user = os.getenv("POSTGRES_USER", "lifeos_user")
        pg_password = os.getenv("POSTGRES_PASSWORD", "postgres")
        pg_db = os.getenv("POSTGRES_DB", "lifeos_edge")
        pg_host = os.getenv("POSTGRES_HOST", "postgres")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        
        self.config["postgres_url"] = self._ensure_asyncpg_url(
            f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        )

    def _resolve_hybrid_profile(self):
        """
        Strict manual mode requiring granular validation of all individual environment variables.
        """
        logger.info("🔀 Resolving 'hybrid' profile credentials (strict mode)...")
        
        qdrant_host = os.getenv("QDRANT_HOST")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        postgres_url = os.getenv("POSTGRES_URL")
        
        if not all([qdrant_host, postgres_url]):
            logger.critical("❌ Missing credentials for 'hybrid' profile. Ensure QDRANT_HOST and POSTGRES_URL are set explicitly.")
            raise ValueError("Incomplete hybrid profile configuration")
            
        self.config["qdrant_host"] = qdrant_host
        self.config["qdrant_api_key"] = qdrant_api_key
        self.config["postgres_url"] = self._ensure_asyncpg_url(postgres_url)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value."""
        return self.config.get(key, default)
        
    def get_llm_config(self) -> dict[str, Any]:
        """Returns LiteLLM / OpenAI base configuration."""
        return {
            "base_url": self.config["litellm_url"],
            "api_key": self.config["litellm_api_key"]
        }
        
    def get_qdrant_config(self) -> dict[str, Any]:
        """Returns Qdrant connection configuration."""
        return {
            "url": self.config["qdrant_host"],
            "api_key": self.config["qdrant_api_key"]
        }
        
    def _ensure_asyncpg_url(self, url: str) -> str:
        """Normalize PostgreSQL URLs for asyncpg use."""
        normalized_url = url.strip()
        if normalized_url.startswith("postgresql+asyncpg://"):
            return normalized_url
        if normalized_url.startswith("postgresql+psycopg2://"):
            return normalized_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        if normalized_url.startswith("postgresql://"):
            return normalized_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if normalized_url.startswith("postgres://"):
            return normalized_url.replace("postgres://", "postgresql+asyncpg://", 1)
        return normalized_url

    def get_postgres_url(self) -> str:
        """Returns PostgreSQL connection string."""
        return self.config["postgres_url"]

    def get_embedding_config(self) -> dict[str, Any]:
        """Returns Embeddings / ZeroShot connection configuration."""
        return {
            "api_base": self.config["embedding_api_base"]
        }

    def get_async_session(self) -> AsyncSession:
        """Returns a new async database session."""
        return AsyncSession(self._async_engine)

config_manager = ConfigManager()
