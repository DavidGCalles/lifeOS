from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from email_validator import validate_email, EmailNotValidError
from src.identity_manager import IdentityManager, UserContext

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
    
    # Estado interno (Contexto)
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        """Inyecta el usuario actual (necesario para saber qué ID actualizar en DB)."""
        self._current_user = user

    # 3. Implementación ASÍNCRONA real
    async def _run(self, email: str) -> str:
        if not self._current_user:
            return "❌ Error: No user context identified. Cannot save email."

        # A. Validación
        try:
            valid = validate_email(email, check_deliverability=False)
            normalized_email = valid.email
        except EmailNotValidError as e:
            return f"❌ Error: Invalid email format. {str(e)}"

        # B. Escritura Asíncrona (IdentityManager ya es async)
        success = await IdentityManager.update_user(
            self._current_user.telegram_id, 
            {"calendar_id": normalized_email}
        )

        if success:
            return (f"✅ Success: Linked email '{normalized_email}' to user '{self._current_user.name}'. "
                    "You can now use calendar tools.")
        else:
            return "❌ Error: Database update failed."

    # 4. Wrapper Async (Vital para FastTrackAgent)
    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)