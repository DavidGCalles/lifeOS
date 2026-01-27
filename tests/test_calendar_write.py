import sys
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

# Path setup para que encuentre src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.calendar_tool import CalendarAddTool
from src.identity_manager import UserContext, UserRole

logging.basicConfig(level=logging.INFO)

def test_calendar_write():
    print("\n>>> 📅 TEST: CalendarAddTool (Writer - Same Day)")

    # 1. Configuración (Requiere la variable de entorno)
    real_email = os.getenv("TEST_CALENDAR_ID")
    if not real_email:
        print("❌ SKIPPING: Export TEST_CALENDAR_ID='tu_email@gmail.com' first.")
        return

    print(f"   👤 Target: {real_email}")
    
    # Contexto Mock
    user = UserContext(telegram_id="999", name="Tester", role=UserRole.ADMIN, calendar_id=real_email)
    
    tool = CalendarAddTool()
    tool.set_context(user)

    # 2. Definir evento para HOY (+1 hora desde ahora)
    now = datetime.now()
    target_dt = now + timedelta(hours=1) 
    target_str = target_dt.strftime("%Y-%m-%d %H:%M")
    
    print(f"   🕒 Scheduling event for TODAY: {target_str}")

    # 3. Ejecución
    result = tool._run(
        summary="🧪 LifeOS Test Event (Immediate)",
        start_time=target_str,
        duration_minutes=60, # 1 Hora de duración
        description="Event created automatically by the CalendarAddTool test suite (ADR-010-005)."
    )

    print("\n   📝 Output:")
    print(result)

    if "Scheduled" in result:
        print("\n   ✅ PASS: Event created successfully. Check your Google Calendar!")
    else:
        print("\n   ❌ FAIL: Could not create event.")

if __name__ == "__main__":
    test_calendar_write()