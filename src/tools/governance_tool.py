from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.managers.identity_manager import IdentityManager, UserContext, UserRole
from src.logging_config import get_logger
from src.utils.telegram_notifier import TelegramNotifier

logger = get_logger(__name__) 

class GovernanceInput(BaseModel):
    telegram_id: str = Field(..., description="The Telegram ID of the user to manage.")
    new_role: str = Field(..., description="The new role. Valid options: 'FAMILY', 'EXTERNAL', 'BLOCKED', 'PENDING'.")
    new_name: str | None = Field(None, description="Optional. A new display name for the user if requested by the Admin.")
    description: str | None = Field(None, description="Critical context about the user (e.g., 'Partner', 'Son', 'Recruiter').")

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

    async def _run(self, telegram_id: str, new_role: str, new_name: str|None = None, description:str|None = None) -> str:
        # 1. Security Check: Only ADMIN can wield The Scepter
        if not self._current_user or not self._current_user.is_admin:
            logger.warning("SECURITY VIOLATION: unauthorized tool use attempted by %s", getattr(self._current_user, 'telegram_id', 'Unknown'))
            return "⛔ SECURITY VIOLATION: You are not authorized to use this tool. Incident reported."
        
        logger.info("UserGovernanceTool invoked by admin %s to update %s -> %s", self._current_user.telegram_id, telegram_id, new_role)
        # 2. Construcción del payload de actualización
        # Aplicamos el fix de .lower() para el Enum de UserRole
        update_data = {"role": new_role.lower()} 
        
        if new_name:
            update_data["name"] = new_name
        
        if description:
            update_data["description"] = description

        # 3. Persistencia en Firestore
        success = await IdentityManager.update_user(telegram_id, update_data)

        if success:
            details = []
            if new_name: details.append(f"name: **{new_name}**")
            if description: details.append(f"desc: *{description}*")
            
            detail_msg = f" ({', '.join(details)})" if details else ""
            logger.info("User %s role updated to %s by admin %s", telegram_id, new_role.upper(), self._current_user.telegram_id)
            
            # NOTIFY THE USER
            try:
                notification = f"🔐 **System Update:** Your role has been updated to **{new_role.upper()}**."
                await TelegramNotifier.send_message(telegram_id, notification)
            except Exception as e:
                logger.warning(f"Failed to notify user {telegram_id}: {e}")

            return f"✅ Decree Executed: User `{telegram_id}` is now **{new_role.upper()}**{detail_msg}."
        else:
            logger.error("Failed to update user %s with %s by admin %s", telegram_id, update_data, self._current_user.telegram_id)
            return "❌ System Error: Could not update Firestore."

    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)