from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.identity_manager import IdentityManager, UserContext, UserRole

class GovernanceInput(BaseModel):
    telegram_id: str = Field(..., description="The Telegram ID of the user to manage.")
    new_role: str = Field(..., description="The new role. Valid options: 'FAMILY', 'EXTERNAL', 'BLOCKED', 'PENDING'.")
    new_name: str | None = Field(None, description="Optional. A new display name for the user if requested by the Admin.")

class UserGovernanceTool(BaseTool):
    name: str = "UserGovernanceTool"
    description: str = (
        "ADMIN ONLY. Use this tool to authorize, block, or change the permissions of a user. "
        "Useful when the Admin replies 'Authorize user X as FAMILY'. "
        "Strictly forbidden for non-admin users."
    )
    args_schema: type[BaseModel] = GovernanceInput
    
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        self._current_user = user

    async def _run(self, telegram_id: str, new_role: str, new_name: str) -> str:
        # 1. Security Check: Only ADMIN can wield The Scepter
        if not self._current_user or not self._current_user.is_admin:
            return "⛔ SECURITY VIOLATION: You are not authorized to use this tool. Incident reported."

        # 2. Preparar el paquete de actualización
        update_data = {"role": new_role.lower()}
        
        if new_name:
            update_data["name"] = new_name

        # 3. Ejecutar en Firestore
        success = await IdentityManager.update_user(telegram_id, update_data)

        if success:
            name_msg = f" with name **{new_name}**" if new_name else ""
            return f"✅ Executed: User `{telegram_id}` is now **{new_role.upper()}**{name_msg}."
        else:
            return "❌ System Error: Could not update Firestore."

        # 3. Execute Order
        success = await IdentityManager.update_user(
            telegram_id, 
            {"role": target_role.value}
        )

        if success:
            return f"✅ Decree Executed: User `{telegram_id}` is now **{target_role.value}**."
        else:
            return "❌ System Error: Could not update Firestore. Check logs."

    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)