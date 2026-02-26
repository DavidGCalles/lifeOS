from datetime import datetime

from pydantic import BaseModel, Field


class SystemStatus(BaseModel):
    """
    Represents the operational status of the system, including user activity
    and health of dependent services.
    """

    last_activity_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp of the last detected user activity.",
    )
    llm_proxy_healthy: bool = Field(
        default=True, description="Health status of the LiteLLM proxy."
    )
