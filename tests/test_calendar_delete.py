import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.calendar_tool import CalendarAddTool, CalendarDeleteTool
from src.identity_manager import UserContext, UserRole

from src.logging_config import configure_logging
configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_delete_lifecycle():
    logger.info("\n>>> 🗑️ TEST: Calendar Delete Lifecycle (Create -> Delete)")

    real_email = os.getenv("TEST_CALENDAR_ID")
    if not real_email:
        logger.warning("❌ SKIPPING: Export TEST_CALENDAR_ID='tu_email@gmail.com' first.")
        return

    user = UserContext(telegram_id="999", name="Tester", role=UserRole.ADMIN, calendar_id=real_email)
    
    adder = CalendarAddTool()
    deleter = CalendarDeleteTool()
    adder.set_context(user)
    deleter.set_context(user)

    # 1. Crear evento único (usando timestamp para evitar colisiones)
    unique_code = datetime.now().strftime("%M%S")
    event_title = f"DeleteMe_Test_{unique_code}"
    start_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M") # Mañana

    logger.info(f"   1️⃣ Creating Dummy Event: '{event_title}'...")
    add_res = adder._run(
        summary=event_title,
        start_time=start_time,
        duration_minutes=15
    )
    
    if "Error" in add_res:
        logger.error(f"   ❌ Setup Failed: {add_res}")
        return

    logger.info("   ✅ Created.")

    # 2. Intentar borrarlo
    logger.info(f"   2️⃣ Attempting to delete using query: '{event_title}'...")
    del_res = deleter._run(query=event_title)
    logger.info(f"   🤖 Output: {del_res}")

    if "DELETED" in del_res and event_title in del_res:
        logger.info("   🎉 SUCCESS: Event deleted cleanly.")
    else:
        logger.error("   ❌ FAIL: Delete operation failed or was ambiguous.")

if __name__ == "__main__":
    test_delete_lifecycle()