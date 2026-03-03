from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from email_validator import validate_email, EmailNotValidError
from src.identity_manager import IdentityManager, UserContext
import logging

logger = logging.getLogger(__name__)

# 1. Definimos el Schema (Input)
class SetEmailInput(BaseModel):
    email: str = Field(..., description="The Google email address to link to the user's profile.")

# 2. La Clase hereda de BaseTool (para contentar al tool_converter y CrewAI)
class SetCalendarIDTool(BaseTool):
    name: str = "SetCalendarIDTool"
    description: str = (
        "Use this tool to SAVE or UPDATE the user's Google Email address. "
        "REQUIRED when the user provides their email for Calendar integration. "
        "Logic: Validates format -> Saves to Firestore."
    )
    args_schema: type[BaseModel] = SetEmailInput
    _current_user: UserContext | None = PrivateAttr(default=None)


    def set_context(self, user: UserContext):
        """Inyecta el usuario actual (necesario para saber qué ID actualizar en DB)."""
        self._current_user = user

    async def _run(self, email: str) -> str:
        try:
            logger.warning("INSIDE TRY")
            logger.info("📧 SetCalendarIDTool invoked with email: %s", email)
            if not self._current_user:
                logger.error("No user context set for SetCalendarIDTool.")
                return "❌ Error: No user context identified."

            # 1. Validación (igual)
            try:
                valid = validate_email(email, check_deliverability=False)
                normalized_email = valid.email
            except EmailNotValidError as e:
                return f"❌ Error: Invalid email format. {str(e)}"

            # 2. Actualización en DB
            success = await IdentityManager.update_user(
                self._current_user.telegram_id, 
                {"calendar_id": normalized_email}
            )
            logger.warning("AFTER DB UPDATE ATTEMPT, SUCCESS=%s", success)
            if success:
                # --- FIX CRÍTICO: ACTUALIZACIÓN EN MEMORIA ("HOT PATCH") ---
                # Esto actualiza la referencia compartida que usan las otras tools
                previous_email = self._current_user.calendar_id
                self._current_user.calendar_id = normalized_email
                
                logger.info(f"🔄 Context Hot-Reload: {previous_email} -> {normalized_email}")
                # -----------------------------------------------------------
                logger.warning("INSIDE SUCCESS")
                return (f"✅ Success: Linked email '{normalized_email}'. "
                        "I have updated my internal records instantly. You can now access the calendar.")
            else:
                logger.warning("INSIDE DB FAILURE")
                return "❌ Error: Database update failed."
        except Exception as e:
            logger.error("Unexpected error in SetCalendarIDTool: %s", str(e))
            return f"❌ Unexpected error: {str(e)}"

    # 4. Wrapper Async (Vital para FastTrackAgent)
    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)