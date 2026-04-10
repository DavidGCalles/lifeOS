import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.managers.postgres_identity_manager import PostgresIdentityManager, UserContext
from src.schemas.db import UserRole, UserStatus


class FakeDBUser:
    def __init__(self, id, name, role, status, description, profile_metadata):
        self.id = id
        self.name = name
        self.role = role
        self.status = status
        self.description = description
        self.profile_metadata = profile_metadata


@pytest.mark.asyncio
async def test_get_user_returns_guest_when_user_not_registered():
    # Mock the config_manager
    with patch('src.managers.postgres_identity_manager.config_manager') as mock_config:
        mock_session = MagicMock()
        mock_config.get_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_config.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.exec = AsyncMock(return_value=result)

        user = await PostgresIdentityManager.get_user(12345)

        assert user.telegram_id == "12345"
        assert user.name == "Stranger"
        assert user.role == UserRole.PENDING
        assert user.description == "Unauthorized"


@pytest.mark.asyncio
async def test_get_user_returns_db_user_with_profile_metadata():
    db_user = FakeDBUser(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Alice",
        role=UserRole.ADMIN,
        status=UserStatus.APPROVED,
        description="System administrator",
        profile_metadata={"calendar_id": "alice@example.com", "department": "operations"},
    )

    with patch('src.managers.postgres_identity_manager.config_manager') as mock_config:
        mock_session = MagicMock()
        mock_config.get_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_config.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = MagicMock()
        result.scalar_one_or_none.return_value = db_user
        mock_session.exec = AsyncMock(return_value=result)

        user = await PostgresIdentityManager.get_user("12345")

        assert user.telegram_id == "12345"
        assert user.name == "Alice"
        assert user.role == UserRole.ADMIN
        assert user.description == "System administrator"
        assert user.calendar_id == "alice@example.com"
        assert user.is_admin is True


@pytest.mark.asyncio
async def test_get_user_handles_invalid_profile_metadata_gracefully(monkeypatch):
    bad_metadata = "not-a-json"
    db_user = FakeDBUser(
        id="00000000-0000-0000-0000-000000000002",
        name="Bob",
        role=UserRole.USER,
        status=UserStatus.PENDING,
        description="Malformed metadata",
        profile_metadata=bad_metadata,
    )

    with patch('src.managers.postgres_identity_manager.config_manager') as mock_config:
        mock_session = MagicMock()
        mock_config.get_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_config.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = MagicMock()
        result.scalar_one_or_none.return_value = db_user
        mock_session.exec = AsyncMock(return_value=result)

        user = await PostgresIdentityManager.get_user("54321")

        assert user.telegram_id == "54321"
        assert user.name == "Bob"
        assert user.role == UserRole.USER
        assert user.description == "Malformed metadata"
        assert user.calendar_id is None


@pytest.mark.asyncio
async def test_register_user_stub_returns_false():
    user = UserContext(
        telegram_id="99999",
        name="Test User",
        role=UserRole.GUEST,
        description="Test stub",
    )
    
    with patch('src.managers.postgres_identity_manager.config_manager') as mock_config:
        mock_session = MagicMock()
        mock_config.get_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_config.get_async_session.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Mock existing check
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.exec = AsyncMock(return_value=result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        result = await PostgresIdentityManager.register_user(user)

        assert result is True
