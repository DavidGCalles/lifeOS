from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.identity_manager import IdentityManager, UserContext, UserRole

class GovernanceInput(BaseModel):
    telegram_id: str = Field(..., description="The Telegram ID of the user to manage.")
    new_role: str = Field(..., description="The new role. Valid options: 'FAMILY', 'EXTERNAL', 'BLOCKED', 'PENDING'.")

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

    async def _run(self, telegram_id: str, new_role: str) -> str:
        # 1. Security Check: Only ADMIN can wield The Scepter
        if not self._current_user or not self._current_user.is_admin:
            return "⛔ SECURITY VIOLATION: You are not authorized to use this tool. Incident reported."

        # 2. Validate Role
        try:
            # Normalize input (handle case sensitivity)
            target_role = UserRole(new_role.upper())
        except ValueError:
            valid_roles = [r.value for r in UserRole]
            return f"❌ Invalid Role. Valid options are: {valid_roles}"

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