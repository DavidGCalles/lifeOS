import sys
import os
import logging
from dotenv import load_dotenv

# Ensure src path is accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Centralized logging
from src.logging_config import configure_logging
configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_google_infrastructure():
    logger.info("\n>>> 🏗️  TESTING GOOGLE INFRASTRUCTURE...")

    try:
        from src.tools.google_base import GoogleServiceFactory
    except ImportError as e:
        logger.error(f"❌ Import Error: {e}")
        return

    # 1. Check Environment
    logger.info("\n1️⃣  Checking Environment Variables...")
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    logger.info(f"   👉 GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")

    if not creds_path:
        logger.error("   ❌ FAIL: Variable not set.")
        return
    
    if not os.path.exists(creds_path):
        logger.error(f"   ❌ FAIL: File does not exist at {creds_path}")
        logger.error("      (Did you remember to mount it in docker-compose?)")
        return
    logger.info("   ✅ PASS: Credentials file found.")

    # 2. Check Authentication & Service Build
    logger.info("\n2️⃣  Attempting Google Auth (Calendar Service)...")
    try:
        # We try to build the Calendar service. If auth fails, this explodes.
        service = GoogleServiceFactory.build_service('calendar', 'v3')
        
        # Optional: Try a dummy API call if you want to be 100% sure
        # But building the service is usually enough to validate the JSON signature.
        logger.info(f"   ✅ PASS: Service object created: {type(service)}")
        
    except Exception as e:
        logger.error(f"   ❌ FAIL: Authentication failed. Details: {e}")
        return

    logger.info("\n🎉 SUCCESS: Google Infrastructure is ready for Tools.")

if __name__ == "__main__":
    test_google_infrastructure()