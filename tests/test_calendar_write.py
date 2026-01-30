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

from src.logging_config import configure_logging
configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_calendar_write():
    logger.info("\n>>> 📅 TEST: CalendarAddTool (Writer - Same Day)")

    # 1. Configuración (Requiere la variable de entorno)
    real_email = os.getenv("TEST_CALENDAR_ID")
    if not real_email:
        logger.warning("❌ SKIPPING: Export TEST_CALENDAR_ID='tu_email@gmail.com' first.")
        return

    logger.info(f"   👤 Target: {real_email}")
    
    # Contexto Mock
    user = UserContext(telegram_id="999", name="Tester", role=UserRole.ADMIN, calendar_id=real_email)
    
    tool = CalendarAddTool()
    tool.set_context(user)

    # 2. Definir evento para HOY (+1 hora desde ahora)
    now = datetime.now()
    target_dt = now + timedelta(hours=1) 
    target_str = target_dt.strftime("%Y-%m-%d %H:%M")
    
    logger.info(f"   🕒 Scheduling event for TODAY: {target_str}")

    # 3. Ejecución
    result = tool._run(
        summary="🧪 LifeOS Test Event (Immediate)",
        start_time=target_str,
        duration_minutes=60, # 1 Hora de duración
        description="Event created automatically by the CalendarAddTool test suite (ADR-010-005)."
    )

    logger.info("\n   📝 Output:")
    logger.info(result)

    if "Scheduled" in result:
        logger.info("\n   ✅ PASS: Event created successfully. Check your Google Calendar!")
    else:
        logger.error("\n   ❌ FAIL: Could not create event.")

if __name__ == "__main__":
    test_calendar_write()