from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from src.identity_manager import IdentityManager, UserRole
from src.logging_config import get_logger

logger = get_logger(__name__)

class PendingUsersInput(BaseModel):
    pass 

class GetPendingUsersTool(BaseTool):
    name: str = "GetPendingUsersTool"
    description: str = (
        "Retrieves a list of all users currently in the 'PENDING' role. "
        "Useful for the Bouncer to review new or unauthorized users awaiting approval."
    )
    args_schema: type[BaseModel] = PendingUsersInput

    async def _run(self) -> str:
        logger.info("GetPendingUsersTool invoked")
        try:
            # We explicitly ask for PENDING users
            pending_users = await IdentityManager.get_users_by_role(UserRole.PENDING)
            
            if not pending_users:
                return "No pending users found."
            
            result = "Found the following Pending Users:\n"
            for user in pending_users:
                result += f"- Name: {user.name}, ID: {user.telegram_id}, Description: {user.description or 'N/A'}\n"
            
            return result
        except Exception as e:
            logger.error(f"Error fetching pending users: {e}")
            return f"Error fetching pending users: {str(e)}"

    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)
