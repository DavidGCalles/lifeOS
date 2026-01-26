import sys
import os
import logging
from dotenv import load_dotenv

# Ensure src path is accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Setup simple logging
logging.basicConfig(level=logging.INFO)

def test_google_infrastructure():
    print("\n>>> 🏗️  TESTING GOOGLE INFRASTRUCTURE...")

    try:
        from src.tools.google_base import GoogleServiceFactory
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        return

    # 1. Check Environment
    print("\n1️⃣  Checking Environment Variables...")
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    print(f"   👉 GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")

    if not creds_path:
        print("   ❌ FAIL: Variable not set.")
        return
    
    if not os.path.exists(creds_path):
        print(f"   ❌ FAIL: File does not exist at {creds_path}")
        print("      (Did you remember to mount it in docker-compose?)")
        return
    print("   ✅ PASS: Credentials file found.")

    # 2. Check Authentication & Service Build
    print("\n2️⃣  Attempting Google Auth (Calendar Service)...")
    try:
        # We try to build the Calendar service. If auth fails, this explodes.
        service = GoogleServiceFactory.build_service('calendar', 'v3')
        
        # Optional: Try a dummy API call if you want to be 100% sure
        # But building the service is usually enough to validate the JSON signature.
        print(f"   ✅ PASS: Service object created: {type(service)}")
        
    except Exception as e:
        print(f"   ❌ FAIL: Authentication failed. Details: {e}")
        return

    print("\n🎉 SUCCESS: Google Infrastructure is ready for Tools.")

if __name__ == "__main__":
    test_google_infrastructure()