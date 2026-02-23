import os
import sys
import pytest

# ensure src is on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import models

from src.identity_manager import UserContext, UserRole
from src.schemas.memory import (
    EpisodicMemoryItem,
    EpisodicMemoryMetadata,
    MemoryCategory,
    MemoryType,
    MemorySource,
)
from src.memory_gateway import MemoryGateway
from src.memory_manager import VectorMemoryManager


@pytest.mark.asyncio
async def test_search_semantic_archive_rbac(monkeypatch):
    """Verify that semantic searches always get an RBAC filter derived from user context."""
    captured: dict = {}

    async def fake_search(self, query, filters=None, limit=5):
        captured['filters'] = filters
        return []

    monkeypatch.setattr(VectorMemoryManager, "search_memory", fake_search)

    user = UserContext(telegram_id="u100", name="Test", role=UserRole.EXTERNAL)
    await MemoryGateway.search_semantic_archive(user_ctx=user, query="hello")

    f = captured.get('filters')
    assert isinstance(f, models.Filter)
    keys = {cond.key for cond in (f.should or [])}
    assert keys == {"owner_id", "visibility"}

    # family role should add extra clause
    user2 = UserContext(telegram_id="u200", name="Fam", role=UserRole.FAMILY)
    captured.clear()
    await MemoryGateway.search_semantic_archive(user_ctx=user2, query="hi")
    f2 = captured.get('filters')
    assert len(f2.should) == 3


@pytest.mark.asyncio
async def test_channel_methods_require_user_context():
    """Both public retrieval channels raise if user_ctx is None."""
    with pytest.raises(ValueError):
        await MemoryGateway.fetch_working_memory(user_ctx=None, chat_id=1)
    with pytest.raises(ValueError):
        await MemoryGateway.search_semantic_archive(user_ctx=None, query="x")


@pytest.mark.asyncio
async def test_fetch_working_memory_delegates(monkeypatch):
    """Ensure Firestore channel simply forwards to _query_session with the same results."""
    user = UserContext(telegram_id="u1", name="u1", role=UserRole.EXTERNAL)
    expected = [{"message_id": "m1", "content": "hello"}]

    async def fake(cls, chat_id, user_ctx, limit=15):
        assert user_ctx is user
        return expected

    monkeypatch.setattr(MemoryGateway, "_query_session", classmethod(fake))
    result = await MemoryGateway.fetch_working_memory(user_ctx=user, chat_id=99, limit=3)
    assert result == expected


@pytest.mark.asyncio
async def test_search_semantic_archive_delegates(monkeypatch):
    """Ensure vector channel simply forwards results from _query_vector."""
    user = UserContext(telegram_id="u2", name="u2", role=UserRole.ADMIN)
    dummy_item = EpisodicMemoryItem(
        content="c",
        metadata=EpisodicMemoryMetadata(
            owner_id="u2",
            category=MemoryCategory.FAMILY,
            type=MemoryType.REFLECTION,
            source=MemorySource.AGENT_REFLECTION,
        ),
    )

    async def fake(cls, query, user_ctx, domain=None, limit=5):
        assert user_ctx is user
        return [dummy_item]

    monkeypatch.setattr(MemoryGateway, "_query_vector", classmethod(fake))
    result = await MemoryGateway.search_semantic_archive(user_ctx=user, query="abc", limit=2)
    assert result == [dummy_item]

@pytest.mark.asyncio
async def test_add_working_memory_and_metadata(monkeypatch):
    """Writing through the gateway should call the SessionManager helper."""
    calls = {}
    async def fake_add(chat_id, message_data):
        calls['chat_id'] = chat_id
        calls['message_data'] = message_data
        return "ok"
    monkeypatch.setattr(SessionManager, "add_message", fake_add)

    user = UserContext(telegram_id="owner1", name="O", role=UserRole.EXTERNAL)
    msg = {"role": "user", "content": "hi"}
    result = await MemoryGateway.add_working_memory(user, 123, msg)
    assert result == "ok"
    assert calls['chat_id'] == 123
    # owner_id should be injected if missing
    assert calls['message_data']['metadata']['owner_id'] == "owner1"

    with pytest.raises(ValueError):
        await MemoryGateway.add_working_memory(None, 1, {})

@pytest.mark.asyncio
async def test_save_and_delete_semantic_memory(monkeypatch):
    """Ensure semantic writes go to the VectorMemoryManager and require context."""
    saved = {}
    async def fake_add(self, item):
        saved['item'] = item
        return "mid"
    async def fake_del(self, mem_id):
        saved['deleted'] = mem_id
    monkeypatch.setattr(VectorMemoryManager, "add_memory", fake_add)
    monkeypatch.setattr(VectorMemoryManager, "delete_memory", fake_del)

    user = UserContext(telegram_id="u1", name="User", role=UserRole.ADMIN)
    from src.schemas.memory import EpisodicMemoryItem, EpisodicMemoryMetadata
    item = EpisodicMemoryItem(
        content="something",
        metadata=EpisodicMemoryMetadata(owner_id="", category=MemoryCategory.FAMILY, type=MemoryType.REFLECTION, source=MemorySource.AGENT_REFLECTION),
    )
    mid = await MemoryGateway.save_semantic_memory(user, item)
    assert mid == "mid"
    assert saved['item'] is item
    # the gateway should fill missing owner_id
    assert item.metadata.owner_id == "u1"

    await MemoryGateway.delete_semantic_memory(user, "abc")
    assert saved['deleted'] == "abc"

    with pytest.raises(ValueError):
        await MemoryGateway.save_semantic_memory(None, item)
    with pytest.raises(ValueError):
        await MemoryGateway.delete_semantic_memory(None, "x")
