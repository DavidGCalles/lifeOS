from datetime import datetime, timedelta, timezone
import logging

import httpx

from src.config import get_litellm_health_url
from src.memory_gateway import MemoryGateway
from src.schemas.system_status import SystemStatus

logger = logging.getLogger(__name__)


class SystemStatusManager:
    """
    Provides a centralized mechanism for operational telemetry, allowing the
    worker to make informed decisions about hardware usage and system
    availability before executing heavy background tasks.
    """

    @staticmethod
    async def is_channel_active(time_window_minutes: int) -> bool:
        """
        Checks if there has been any user activity within the specified time
        window by checking the last activity timestamp in the system status.
        """
        status = await MemoryGateway.get_system_status()
        if not status:
            return False

        last_activity = status.last_activity_timestamp
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        return (now - last_activity) < timedelta(minutes=time_window_minutes)

    @staticmethod
    async def get_idle_time() -> int:
        """
        Returns the exact number of minutes since the last user message.
        """
        status = await MemoryGateway.get_system_status()
        if not status:
            return -1

        last_activity = status.last_activity_timestamp
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        idle_delta = now - last_activity
        return int(idle_delta.total_seconds() / 60)

    @staticmethod
    async def is_llm_proxy_healthy() -> bool:
        """
        Performs a lightweight health check to the LiteLLM container.
        """
        health_url = get_litellm_health_url()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)
                is_healthy = response.status_code == 200

                status = await MemoryGateway.get_system_status()
                if status:
                    status.llm_proxy_healthy = is_healthy
                    await MemoryGateway.update_system_status(status)

                return is_healthy
        except httpx.RequestError as e:
            logger.error(f"LiteLLM health check failed: {e}")

            status = await MemoryGateway.get_system_status()
            if status:
                status.llm_proxy_healthy = False
                await MemoryGateway.update_system_status(status)

            return False

    @staticmethod
    async def record_activity():
        """
        Records a new activity timestamp, updating the system status.
        """
        status = await MemoryGateway.get_system_status()
        if not status:
            status = SystemStatus()

        status.last_activity_timestamp = datetime.now(timezone.utc)
        await MemoryGateway.update_system_status(status)
