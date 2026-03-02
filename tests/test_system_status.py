from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.cloud.firestore import DocumentSnapshot

from src.schemas.system_status import SystemStatus
from src.system_status import SystemStatusManager


@pytest.fixture
def mock_memory_gateway():
    """Fixture for a mocked MemoryGateway."""
    with patch("src.system_status.MemoryGateway") as mock:
        mock.get_system_status = AsyncMock()
        mock.update_system_status = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_is_channel_active_true(mock_memory_gateway):
    """Test is_channel_active returns True when activity is recent."""
    now = datetime.now(timezone.utc)
    last_activity = now - timedelta(minutes=5)
    mock_memory_gateway.get_system_status.return_value = SystemStatus(
        last_activity_timestamp=last_activity
    )

    assert await SystemStatusManager.is_channel_active(time_window_minutes=10)


@pytest.mark.asyncio
async def test_is_channel_active_false(mock_memory_gateway):
    """Test is_channel_active returns False for old activity."""
    last_activity = datetime.now(timezone.utc) - timedelta(minutes=15)
    mock_memory_gateway.get_system_status.return_value = SystemStatus(
        last_activity_timestamp=last_activity
    )

    assert not await SystemStatusManager.is_channel_active(time_window_minutes=10)


@pytest.mark.asyncio
async def test_get_idle_time(mock_memory_gateway):
    """Test get_idle_time returns correct idle time in minutes."""
    last_activity = datetime.now(timezone.utc) - timedelta(minutes=20)
    mock_memory_gateway.get_system_status.return_value = SystemStatus(
        last_activity_timestamp=last_activity
    )

    idle_time = await SystemStatusManager.get_idle_time()
    assert idle_time >= 20

@pytest.mark.asyncio
async def test_record_activity(mock_memory_gateway):
    """Test record_activity updates the timestamp."""
    mock_memory_gateway.get_system_status.return_value = None

    await SystemStatusManager.record_activity()
    mock_memory_gateway.update_system_status.assert_called_once()
    new_status = mock_memory_gateway.update_system_status.call_args[0][0]
    assert isinstance(new_status, SystemStatus)
    time_diff = datetime.now(timezone.utc) - new_status.last_activity_timestamp
    assert time_diff.total_seconds() < 5
