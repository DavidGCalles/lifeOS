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
        'https://www.googleapis.com/auth/calendar.events'
    ]

    @staticmethod
    def get_credentials(scopes: list[str] | None = None) -> service_account.Credentials:
        """
        Loads credentials from the JSON file defined in env vars.
        """
        target_scopes = scopes or GoogleServiceFactory.DEFAULT_SCOPES
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

        if not creds_path:
            error_msg = "❌ CRITICAL: GOOGLE_APPLICATION_CREDENTIALS env var is not set."
            logger.error(error_msg)
            raise EnvironmentError(error_msg)

        if not os.path.exists(creds_path):
            error_msg = f"❌ CRITICAL: Credentials file not found at: {creds_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            logger.info(f"🔑 Loading Google Credentials from: {creds_path}")
            creds = service_account.Credentials.from_service_account_file(
                creds_path, 
                scopes=target_scopes
            )
            return creds
        except Exception as e:
            logger.error(f"❌ Failed to load Service Account credentials: {e}")
            raise

    @staticmethod
    def build_service(service_name: str, version: str = 'v3', scopes: list[str] | None = None) -> Resource:
        """
        Builds an authenticated API client (e.g., 'calendar', 'v3').
        """
        try:
            creds = GoogleServiceFactory.get_credentials(scopes)
            service = build(service_name, version, credentials=creds, cache_discovery=False)
            logger.info(f"🔌 Google Service '{service_name} ({version})' built successfully.")
            return service
        except Exception as e:
            logger.error(f"❌ Failed to build Google Service '{service_name}': {e}")
            raise