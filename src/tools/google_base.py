import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from google.auth.exceptions import DefaultCredentialsError

logger = logging.getLogger(__name__)

class GoogleServiceFactory:
    """
    Centralized factory to authenticate and build Google Service Clients.
    It relies on the 'GOOGLE_APPLICATION_CREDENTIALS' environment variable 
    injected via Docker.
    """
    
    # Default scopes needed for LifeOS (Calendar & Drive usually go together)
    DEFAULT_SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/drive.readonly'
    ]
    _services: dict[str, Resource] = {}
    _creds: service_account.Credentials | None = None

    @classmethod
    def get_credentials(cls, scopes: list[str] = None) -> service_account.Credentials:
        """Carga credenciales (Lazy Loading + Caching)."""
        if cls._creds:
            return cls._creds

        target_scopes = scopes or cls.DEFAULT_SCOPES
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

        if not creds_path or not os.path.exists(creds_path):
            raise FileNotFoundError(f"❌ CRITICAL: Credentials not found at {creds_path}")

        try:
            logger.info(f"🔑 Loading Google Credentials from disk...")
            cls._creds = service_account.Credentials.from_service_account_file(
                creds_path, scopes=target_scopes
            )
            return cls._creds
        except Exception as e:
            logger.error(f"❌ Failed to load credentials: {e}")
            raise

    @classmethod
    def build_service(cls, service_name: str, version: str = 'v3', scopes: list[str] = None) -> Resource:
        """Devuelve un servicio autenticado (Reutiliza conexión si existe)."""
        cache_key = f"{service_name}_{version}"
        
        if cache_key in cls._services:
            return cls._services[cache_key]

        try:
            creds = cls.get_credentials(scopes)
            # Construimos el servicio
            service = build(service_name, version, credentials=creds, cache_discovery=False)
            
            # Lo guardamos en caché
            cls._services[cache_key] = service
            logger.info(f"🔌 Service '{cache_key}' built and cached.")
            return service
        except Exception as e:
            logger.error(f"❌ Failed to build service '{service_name}': {e}")
            raise