from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import httpx
import os
import asyncio
from src.logging_config import get_logger
from src.identity_manager import UserContext
from src.utils.telegram_notifier import TelegramNotifier

logger = get_logger(__name__)

class DelegateCalendarAuditInput(BaseModel):
    """Input schema for delegating a calendar audit."""
    audit_focus: str = Field(..., description="The focus of the audit (e.g., 'Check for conflicts', 'Optimize for deep work').")

class DelegateCalendarAuditTool(BaseTool):
    name: str = "delegate_calendar_audit"
    description: str = (
        "Delegates a deep audit of the calendar to a background specialist. "
        "Use this when the user asks for a comprehensive review of their schedule, "
        "optimization of time blocks, or identification of inefficiencies."
    )
    args_schema: type[BaseModel] = DelegateCalendarAuditInput
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        """Injects the current user context before executing the tool."""
        self._current_user = user

    async def _arun(self, audit_focus: str) -> str:
        """
        Invokes the tool asynchronously to delegate the calendar audit to a background worker.
        """
        if not self._current_user:
            return "Error: User context is not set. Cannot delegate audit."

        logger.info(f"Delegating calendar audit for user {self._current_user.telegram_id} with focus: {audit_focus}")

        # 1. Directly send acknowledgment to the user via Telegram
        acknowledgment_message = "Voy a revisar tu calendario en profundidad... Te aviso con mis conclusiones."
        await TelegramNotifier.send_message(self._current_user.telegram_id, acknowledgment_message)

        # 2. Prepare payload and headers for the worker
        # Stub endpoint for now
        worker_url = os.getenv("WORKER_HOST")
        if not worker_url:
           raise ValueError("WORKER_HOST environment variable is not set. Cannot dispatch audit task.")
        else:
            worker_url = f"{worker_url}/system/tasks/calendar_audit"
        api_key = os.getenv("INTERNAL_API_KEY")
        headers = {"Authorization": f"Bearer {api_key}"}
        
        payload = {
            "user_id": self._current_user.telegram_id,
            "session_id": self._current_user.session_id,
            "audit_focus": audit_focus
        }

        # 3. Asynchronously dispatch the task (fire-and-forget)
        async def dispatch_task():
            try:
                # For now, since it is a stub, we might not even have the endpoint running. 
                # But following instructions "endpoint ... will be a stub", I assume we try to call it.
                # If the user meant the tool implementation should be a stub, then I wouldn't call the network.
                # But "endpoint ... will be a stub" implies the backend side is the stub.
                # However, to avoid errors if the backend is not ready, I might wrap this in a try/except that is tolerant.
                async with httpx.AsyncClient() as client:
                    # We can use a short timeout since it's fire-and-forget logic (though here we await the request?)
                    # The original code awaits the request but wraps the whole dispatch_task in asyncio.create_task
                    await client.post(worker_url, json=payload, headers=headers, timeout=5)
                logger.info("Audit task successfully dispatched to worker for user %s.", self._current_user.telegram_id)
            except httpx.RequestError as e:
                logger.error(f"Failed to dispatch audit task to worker for user %s: {e}", self._current_user.telegram_id)

        asyncio.create_task(dispatch_task())

        # 4. Return a silent stop message to the LLM
        return "TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY"

    def _run(self, audit_focus: str) -> str:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self._arun(audit_focus))
