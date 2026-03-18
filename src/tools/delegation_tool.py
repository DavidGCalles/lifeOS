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
        if not self._current_user:
            return "Error: User context is not set."

        logger.info(f"Delegating deep thought for user {self._current_user.telegram_id}...")

        # 1. Notificación al usuario (OK)
        await TelegramNotifier.send_message(self._current_user.telegram_id, "Voy a buscar...")

        # 2. Configuración (OK)
        worker_url = os.getenv("WORKER_URL", "http://localhost:8001/system/tasks/deep_analysis")
        payload = { ... }

        # 3. CAMBIO CRÍTICO: Esperar al POST
        try:
            async with httpx.AsyncClient() as client:
                # Esperamos a que el worker responda al menos un 202 Accepted o 200 OK
                headers = {"Authorization": os.getenv("INTERNAL_API_KEY", "")}
                response = await client.post(worker_url, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                logger.info("✅ Task ACKNOWLEDGED by worker.")
        except Exception as e:
            logger.error(f"❌ Worker unreachable: {e}")
            return f"Error: No pude contactar con el sistema de análisis profundo. {str(e)}"

        # 4. Ahora sí, cortamos el flujo del agente
        return "TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY"

    def _run(self, user_request: str) -> str:
        """Synchronous wrapper for the async run method."""
        # This is a fallback, but the agent should ideally call _arun.
        return asyncio.run(self._arun(user_request))
