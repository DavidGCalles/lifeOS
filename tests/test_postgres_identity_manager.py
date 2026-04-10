import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# ensure src is on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.managers.postgres_identity_manager import PostgresIdentityManager, UserContext
from src.schemas.db import UserRole, UserStatus


class FakeDBUser:
    def __init__(self, _user_id, name, role, status, description, profile_metadata):
        self.id = _user_id
        self.name = name
        self.role = role
        self.status = status
        self.description = description
        self.profile_metadata = profile_metadata


@pytest.mark.asyncio
async def test_get_user_returns_guest_when_user_not_registered():
    mock_repo = MagicMock()
    mock_repo.get_user_by_telegram_id = AsyncMock(return_value=None)
    manager = PostgresIdentityManager(mock_repo)

    user = await manager.get_user(12345)

    assert user.telegram_id == "12345"
    assert user.name == "Stranger"
    assert user.role == UserRole.GUEST
    assert user.status == UserStatus.PENDING
    assert user.description == "Unauthorized"


@pytest.mark.asyncio
async def test_get_user_returns_db_user_with_profile_metadata():
    db_user = FakeDBUser(
        uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Alice",
        role=UserRole.ADMIN,
        status=UserStatus.APPROVED,
        description="System administrator",
        profile_metadata={"calendar_id": "alice@example.com", "department": "operations"},
    )

    mock_repo = MagicMock()
    mock_repo.get_user_by_telegram_id = AsyncMock(return_value=db_user)
    manager = PostgresIdentityManager(mock_repo)

    user = await manager.get_user("12345")

    assert user.telegram_id == "12345"
    assert user.name == "Alice"
    assert user.role == UserRole.ADMIN
    assert user.description == "System administrator"
    assert user.calendar_id == "alice@example.com"
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_get_user_handles_invalid_profile_metadata_gracefully():
    bad_metadata = "not-a-json"
    db_user = FakeDBUser(
        "00000000-0000-0000-0000-000000000002",
        name="Bob",
        role=UserRole.USER,
        status=UserStatus.PENDING,
        description="Malformed metadata",
        profile_metadata=bad_metadata,
    )

    mock_repo = MagicMock()
    mock_repo.get_user_by_telegram_id = AsyncMock(return_value=db_user)
    manager = PostgresIdentityManager(mock_repo)

    user = await manager.get_user("54321")

    assert user.telegram_id == "54321"
    assert user.name == "Bob"
    assert user.role == UserRole.USER
    assert user.description == "Malformed metadata"
    assert user.calendar_id is None


@pytest.mark.asyncio
async def test_register_user_uses_repository_and_returns_true():
    user = UserContext(
        telegram_id="99999",
        name="Test User",
        role=UserRole.GUEST,
        status=UserStatus.PENDING,
        description="Test stub",
    )

    mock_repo = MagicMock()
    mock_repo.has_telegram_identity = AsyncMock(return_value=False)
    mock_repo.create_user_with_identity = AsyncMock()
    manager = PostgresIdentityManager(mock_repo)

    result = await manager.register_user(user)

    assert result is True
    mock_repo.has_telegram_identity.assert_awaited_once_with(user.telegram_id)
    mock_repo.create_user_with_identity.assert_awaited_once()
