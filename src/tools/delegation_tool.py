from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import httpx
import os
import asyncio
from src.logging_config import get_logger
from src.identity_manager import UserContext
from src.utils.telegram_notifier import TelegramNotifier

logger = get_logger(__name__)

class DelegateDeepThoughtInput(BaseModel):
    """Input schema for delegating a complex task."""
    user_request: str = Field(..., description="The user's detailed and complex request for deep analysis.")

class DelegateDeepThoughtTool(BaseTool):
    name: str = "delegate_deep_thought"
    description: str = (
        "When a user's request is 'dense'—requiring deep synthesis, relationship analysis, "
        "complex memory parsing, or document processing—use this tool. It delegates the "
        "heavy lifting to a background worker, avoiding timeouts and providing a better "
        "user experience. Use for questions that require 'thinking' or 'analyzing'."
    )
    args_schema: type[BaseModel] = DelegateDeepThoughtInput
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        """Injects the current user context before executing the tool."""
        self._current_user = user

    async def _arun(self, user_request: str) -> str:
        """
        Invokes the tool asynchronously to delegate a complex task to a background worker.
        """
        if not self._current_user:
            return "Error: User context is not set. Cannot delegate task."

        logger.info(f"Delegating deep thought for user {self._current_user.telegram_id} with request: {user_request}")

        # 1. Directly send acknowledgment to the user via Telegram
        acknowledgment_message = "Voy a buscar y ordenar bien en la memoria... Te aviso cuando tenga una respuesta."
        await TelegramNotifier.send_message(self._current_user.telegram_id, acknowledgment_message)

        # 2. Prepare payload and headers for the worker
        worker_url = os.getenv("WORKER_URL", "http://localhost:8001/system/tasks/deep_analysis")
        api_key = os.getenv("INTERNAL_API_KEY")
        headers = {"Authorization": f"Bearer {api_key}"}
        
        payload = {
            "user_id": self._current_user.telegram_id,
            "session_id": self._current_user.session_id,
            "user_request": user_request
        }

        # 3. Asynchronously dispatch the task (fire-and-forget)
        async def dispatch_task():
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(worker_url, json=payload, headers=headers, timeout=5)
                logger.info("Task successfully dispatched to worker for user %s.", self._current_user.telegram_id)
            except httpx.RequestError as e:
                logger.error(f"Failed to dispatch task to worker for user %s: {e}", self._current_user.telegram_id)

        asyncio.create_task(dispatch_task())

        # 4. Return a silent stop message to the LLM
        return "TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY"

    def _run(self, user_request: str) -> str:
        """Synchronous wrapper for the async run method."""
        # This is a fallback, but the agent should ideally call _arun.
        return asyncio.run(self._arun(user_request))
