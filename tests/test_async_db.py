import sys
import os
import asyncio
import logging

# Setup path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.session_manager import SessionManager
from src.identity_manager import IdentityManager

# Config logs para ver si Firestore se queja
logging.basicConfig(level=logging.INFO)

async def test_async_infrastructure():
    print("\n>>> 🧪 TEST: Async Infrastructure (Identity & Session)")
    
    # Simula un ID de Telegram
    test_id = 999999999 

    # 1. Test Identity (Async Read)
    print("\n1️⃣  Testing IdentityManager.get_user(Async)...")
    try:
        user = await IdentityManager.get_user(test_id)
        print(f"   ✅ User retrieved: {user.name} | Role: {user.role}")
        print(f"   (Si sale 'Stranger' es normal si no estás en la DB, lo importante es que no explotó)")
    except Exception as e:
        print(f"   ❌ Identity Error: {e}")

    # 2. Test Session Write (Async Write)
    print("\n2️⃣  Testing SessionManager.add_message(Async)...")
    try:
        await SessionManager.add_message(
            chat_id=test_id,
            message_data={
                "role": "user",
                "content": "TEST ASYNC MESSAGE",
                "user_id": test_id,
                "name": "TestRunner"
            }
        )
        print("   ✅ Message write awaited successfully.")
    except Exception as e:
        print(f"   ❌ Write Error: {e}")

    # 3. Test Session Read (Async Read Iterator)
    print("\n3️⃣  Testing SessionManager.get_context(Async Iterator)...")
    try:
        history = await SessionManager.get_context(test_id, limit=5)
        print(f"   ✅ Context retrieved. Items: {len(history)}")
        for msg in history:
            print(f"      - {msg.get('content')}")
    except Exception as e:
        print(f"   ❌ Read Error: {e}")

if __name__ == "__main__":
    if os.getenv("USE_FIRESTORE", "False").lower() != "true":
        print("⚠️  WARNING: USE_FIRESTORE no está en 'true'. Este test usará fallbacks locales/noop.")
    
    asyncio.run(test_async_infrastructure())