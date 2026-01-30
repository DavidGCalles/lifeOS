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

from src.logging_config import configure_logging
configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_calendar_tool_logic():
    logger.info("\n>>> 📅 TEST: CalendarListTool Logic")

    # CASE 1: Usuario SIN email configurado
    logger.info("\n1️⃣  Testing MISSING Calendar ID...")
    user_no_email = UserContext(
        telegram_id="123", name="NoEmailUser", role=UserRole.USER, calendar_id=None
    )
    
    tool = CalendarListTool()
    tool.set_context(user_no_email)
    
    result = tool._run() # Llamamos a _run directo para testear sync
    logger.info(f"   🤖 Output: {result}")
    
    if "Ask the user" in result:
        logger.info("   ✅ PASS: Correctly handled missing email.")
    else:
        logger.error("   ❌ FAIL: Did not return instruction to ask user.")

    # CASE 2: Usuario CON email (Simulamos lectura real si tienes el env var)
    # Para que esto funcione, usa el email que configuraste en el paso anterior
    real_email = os.getenv("TEST_CALENDAR_ID")
    
    if not real_email:
        logger.warning("\n⚠️  Skipping REAL API test (TEST_CALENDAR_ID not set).")
        logger.info("   Export TEST_CALENDAR_ID='tu_email@gmail.com' to test Google connection.")
        return

    logger.info(f"\n2️⃣  Testing REAL Calendar Read for: {real_email}...")
    user_with_email = UserContext(
        telegram_id="456", name="RealUser", role=UserRole.USER, calendar_id=real_email
    )
    
    tool.set_context(user_with_email)
    result_real = tool._run(days_ahead=3)
    
    logger.info("   📝 Resultado Real:")
    logger.info(result_real)
    
    if "Error" not in result_real:
        logger.info("   ✅ PASS: API Call successful.")
    else:
        logger.error("   ❌ FAIL: API Call returned error (Check permissions?).")

if __name__ == "__main__":
    test_calendar_tool_logic()