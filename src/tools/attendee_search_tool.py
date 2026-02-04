import asyncio
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import List
from src.identity_manager import IdentityManager, UserContext
from src.logging_config import get_logger

logger = get_logger(__name__)

class AttendeeSearchInput(BaseModel):
    names: List[str] = Field(..., description="A list of names to search for among known users to invite to an event.")

class AttendeeSearchTool(BaseTool):
    name: str = "AttendeeSearchTool"
    description: str = (
        "Searches for known users by name and returns their email addresses (calendar IDs) "
        "for inviting them to calendar events. Takes a list of names as input." 
        "It will only return emails for users explicitly known to the system." 
    )
    args_schema: type[BaseModel] = AttendeeSearchInput
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        """Injects the current user to maintain architectural consistency."""
        self._current_user = user

    async def _arun(self, names: List[str]) -> str:
        resolved_emails = []
        unresolved_names = []

        for name in names:
            user = await IdentityManager.get_user_by_name(name)
            if user and user.calendar_id:
                resolved_emails.append(user.calendar_id)
                logger.info(f"Found attendee '{name}' with email '{user.calendar_id}'")
            else:
                unresolved_names.append(name)
                logger.warning(f"Attendee '{name}' not found or has no calendar_id.")
        
        if not resolved_emails:
            return "❌ No attendees found with valid emails among the provided names."
        
        result = f"✅ Attendee emails found: {','.join(resolved_emails)}"
        if unresolved_names:
            result += f"\n❓ Could not find: {', '.join(unresolved_names)}"
        
        return result

    def _run(self, names: List[str]) -> str:
        # This synchronous wrapper allows the async tool to be used in a sync context.
        return asyncio.run(self._arun(names))
