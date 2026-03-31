import sys, os
import uuid
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

from src.schemas.db import (
    DBUser,
    DBTelegramIdentity,
    DBSession,
    DBTask,
    DBMessage,
    UserRole,
    UserStatus,
    SessionStatus,
    TaskStatus,
)
from src.schemas.memory import MemoryVisibility, MemoryDomainType


def test_db_user_defaults():
    user = DBUser()
    assert isinstance(user.id, uuid.UUID)
    assert user.role == UserRole.GUEST
    assert user.status == UserStatus.PENDING
    assert user.created_at is not None

def test_db_telegram_identity_instantiation():
    user_id = uuid.uuid4()
    identity = DBTelegramIdentity(telegram_id=123456789, user_id=user_id)
    assert identity.telegram_id == 123456789
    assert identity.user_id == user_id
    assert identity.created_at is not None

def test_db_session_defaults():
    user_id = uuid.uuid4()
    session = DBSession(user_id=user_id)
    assert isinstance(session.id, uuid.UUID)
    assert session.user_id == user_id
    assert session.status == SessionStatus.ACTIVE
    assert session.created_at is not None
    assert session.updated_at is not None

def test_db_task_defaults():
    session_id = uuid.uuid4()
    task = DBTask(session_id=session_id)
    assert isinstance(task.id, uuid.UUID)
    assert task.session_id == session_id
    assert task.status == TaskStatus.PENDING
    assert task.payload == {}
    assert task.created_at is not None
    assert task.updated_at is not None

def test_db_message_defaults():
    session_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    msg = DBMessage(
        session_id=session_id,
        role="user",
        content="Hello world",
        input_type="text",
        owner_id=owner_id
    )
    assert isinstance(msg.id, uuid.UUID)
    assert msg.session_id == session_id
    assert msg.role == "user"
    assert msg.content == "Hello world"
    assert msg.name is None
    assert msg.input_type == "text"
    assert msg.agent_key is None
    assert msg.consolidated is False
    assert msg.owner_id == owner_id
    assert msg.visibility == MemoryVisibility.PRIVATE
    assert msg.domain == MemoryDomainType.EPISODIC
    assert msg.created_at is not None
