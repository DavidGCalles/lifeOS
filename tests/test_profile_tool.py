import sys
import os
import asyncio
import logging
from uuid import uuid4
from dotenv import load_dotenv
load_dotenv()   

# Path setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.profile_tool import SetCalendarIDTool
from src.identity_manager import IdentityManager, UserContext, UserRole

logging.basicConfig(level=logging.INFO)

async def test_set_email():
    print("\n>>> 📧 TEST: SetCalendarIDTool")

    # 1. Crear contexto Mock
    test_id = f"test_user_{uuid4().hex[:8]}"
    user = UserContext(
        telegram_id=test_id,
        name="Tool Tester",
        role=UserRole.USER
    )
    print(f"   👤 User: {test_id}")

    # 2. Inicializar Tool e Inyectar Contexto
    tool = SetCalendarIDTool()
    tool.set_context(user)

    # 3. Ejecutar Tool (Simular Agente)
    target_email = "tester@example.com"
    print(f"   👉 Setting email to: {target_email}")
    
    result = await tool.run(email=target_email)
    print(f"   🤖 Tool Output: {result}")

    if "Success" not in result:
        print("   ❌ FAIL: Tool execution returned error.")
        return

    # 4. Verificación en DB
    print("   🔍 Verifying in Firestore...")
    updated_user = await IdentityManager.get_user(test_id)
    
    if updated_user.calendar_id == target_email:
        print(f"   ✅ PASS: Firestore reflects 'calendar_id': {updated_user.calendar_id}")
    else:
        print(f"   ❌ FAIL: Expected {target_email}, got {updated_user.calendar_id}")

if __name__ == "__main__":
    if not os.getenv("USE_FIRESTORE"):
         print("⚠️  WARNING: USE_FIRESTORE not set. Test might fail.")
    asyncio.run(test_set_email())