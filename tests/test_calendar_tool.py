import sys
import os
import logging
from uuid import uuid4
from dotenv import load_dotenv
load_dotenv()

# Path setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.calendar_tool import CalendarListTool
from src.identity_manager import UserContext, UserRole

logging.basicConfig(level=logging.INFO)

def test_calendar_tool_logic():
    print("\n>>> 📅 TEST: CalendarListTool Logic")

    # CASE 1: Usuario SIN email configurado
    print("\n1️⃣  Testing MISSING Calendar ID...")
    user_no_email = UserContext(
        telegram_id="123", name="NoEmailUser", role=UserRole.USER, calendar_id=None
    )
    
    tool = CalendarListTool()
    tool.set_context(user_no_email)
    
    result = tool._run() # Llamamos a _run directo para testear sync
    print(f"   🤖 Output: {result}")
    
    if "Ask the user" in result:
        print("   ✅ PASS: Correctly handled missing email.")
    else:
        print("   ❌ FAIL: Did not return instruction to ask user.")

    # CASE 2: Usuario CON email (Simulamos lectura real si tienes el env var)
    # Para que esto funcione, usa el email que configuraste en el paso anterior
    real_email = os.getenv("TEST_CALENDAR_ID")
    
    if not real_email:
        print("\n⚠️  Skipping REAL API test (TEST_CALENDAR_ID not set).")
        print("   Export TEST_CALENDAR_ID='tu_email@gmail.com' to test Google connection.")
        return

    print(f"\n2️⃣  Testing REAL Calendar Read for: {real_email}...")
    user_with_email = UserContext(
        telegram_id="456", name="RealUser", role=UserRole.USER, calendar_id=real_email
    )
    
    tool.set_context(user_with_email)
    result_real = tool._run(days_ahead=3)
    
    print("   📝 Resultado Real:")
    print(result_real)
    
    if "Error" not in result_real:
        print("   ✅ PASS: API Call successful.")
    else:
        print("   ❌ FAIL: API Call returned error (Check permissions?).")

if __name__ == "__main__":
    test_calendar_tool_logic()