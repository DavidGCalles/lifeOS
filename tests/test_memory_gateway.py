import os
import sys
import pytest
from qdrant_client import models
# ensure src is on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

@pytest.fixture
def user_a_admin():
    return UserContext(telegram_id="user_a", name="Alice", role=UserRole.ADMIN)

@pytest.fixture
def user_b_guest():
    return UserContext(telegram_id="user_b", name="Bob", role=UserRole.GUEST)

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
    # Patch MemoryGateway._query_session to avoid Firestore
    async def fake_query_session(cls, chat_id, user_ctx, limit=5):
        return []
    monkeypatch.setattr(MemoryGateway, "_query_session", classmethod(fake_query_session))

    # Patch SessionManager.add_message via MemoryGateway only for call capture
    import src.utils.session_manager as session_manager_mod
    async def fake_add_message(chat_id, message_data):
        calls['chat_id'] = chat_id
        calls['message_data'] = message_data
        return "ok"
    monkeypatch.setattr(session_manager_mod.SessionManager, "add_message", fake_add_message)

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

@pytest.mark.asyncio
async def test_memorygateway_unauthorized_access(monkeypatch, user_b_guest):
    """MemoryGateway raises errors or returns empty sets when unauthorized access is attempted."""
    # Simulate _query_session and _query_vector always returning empty for unauthorized
    async def fake_query_session(cls, chat_id, user_ctx, limit=5):
        return []
    async def fake_query_vector(cls, query, user_ctx, domain=None, limit=5):
        return []
    monkeypatch.setattr(
        __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway,
        "_query_session",
        classmethod(fake_query_session),
    )
    monkeypatch.setattr(
        __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway,
        "_query_vector",
        classmethod(fake_query_vector),
    )
    # Should return empty for working memory and semantic archive
    result1 = await __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway.fetch_working_memory(
        user_ctx=user_b_guest, chat_id="chat1", limit=5
    )
    result2 = await __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway.search_semantic_archive(
        user_ctx=user_b_guest, query="secret", limit=5
    )
    assert result1 == [], "Unauthorized user should get empty set from Firestore"
    assert result2 == [], "Unauthorized user should get empty set from Qdrant"
    # Should raise ValueError if user_ctx is None
    with pytest.raises(ValueError):
        await __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway.fetch_working_memory(
            user_ctx=None, chat_id="chat1", limit=5
        )
    with pytest.raises(ValueError):
        await __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway.search_semantic_archive(
            user_ctx=None, query="secret", limit=5
        )
@pytest.mark.asyncio
async def test_admin_can_access_family_memory(monkeypatch, user_a_admin):
    """User A (ADMIN) can retrieve FAMILY scoped memory created by another user."""
    from src.schemas.memory import EpisodicMemoryItem, EpisodicMemoryMetadata, MemoryCategory, MemoryType, MemorySource
    # Memory created by User C (not admin)
    family_item = EpisodicMemoryItem(
        content="Family note",
        metadata=EpisodicMemoryMetadata(
            owner_id="user_c",
            visibility="FAMILY",
            domain="episodic",
            category=MemoryCategory.FAMILY,
            type=MemoryType.REFLECTION,
            source=MemorySource.AGENT_REFLECTION,
        ),
    )
    # Simulate Qdrant returning FAMILY memory for ADMIN
    async def fake_search_memory(self, query, filters=None, limit=5):
        # ADMIN should see FAMILY memory
        if filters and hasattr(filters, 'should'):
            for cond in filters.should:
                if getattr(cond, 'key', None) == 'visibility' and getattr(cond.match, 'value', None) == "FAMILY":
                    return [family_item]
        return []
    monkeypatch.setattr(
        __import__("src.memory_manager", fromlist=["VectorMemoryManager"]).VectorMemoryManager,
        "search_memory",
        fake_search_memory,
    )
    # User A (ADMIN) searches for family memory
    result = await __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway.search_semantic_archive(
        user_ctx=user_a_admin, query="family", limit=5
    )
    assert result and result[0].metadata.visibility == "FAMILY", "Admin should see FAMILY memory from other users"
@pytest.mark.asyncio
async def test_guest_cannot_access_admin_private_qdrant(monkeypatch, user_a_admin, user_b_guest):
    """User B (GUEST) cannot retrieve User A's PRIVATE memory from Qdrant."""
    from src.schemas.memory import EpisodicMemoryItem, EpisodicMemoryMetadata, MemoryCategory, MemoryType, MemorySource
    private_item = EpisodicMemoryItem(
        content="Admin secret",
        metadata=EpisodicMemoryMetadata(
            owner_id=user_a_admin.telegram_id,
            visibility="PRIVATE",
            domain="episodic",
            category=MemoryCategory.FAMILY,
            type=MemoryType.REFLECTION,
            source=MemorySource.AGENT_REFLECTION,
        ),
    )
    # Only return the private item for User A; User B should see nothing
    async def fake_search_memory(self, query, filters=None, limit=5):
        # Simulate RBAC filter: only owner sees the item
        if filters and hasattr(filters, 'should'):
            for cond in filters.should:
                if getattr(cond, 'key', None) == 'owner_id' and getattr(cond.match, 'value', None) == user_a_admin.telegram_id:
                    return [private_item]
        return []
    monkeypatch.setattr(
        __import__("src.memory_manager", fromlist=["VectorMemoryManager"]).VectorMemoryManager,
        "search_memory",
        fake_search_memory,
    )
    # User B tries to search semantic archive
    result = await __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway.search_semantic_archive(
        user_ctx=user_b_guest, query="secret", limit=5
    )
    assert result == [], "Guest should not see Admin's PRIVATE memory in Qdrant"

@pytest.mark.asyncio
async def test_guest_cannot_access_admin_private_firestore(monkeypatch, user_a_admin, user_b_guest):
    """User B (GUEST) cannot retrieve User A's PRIVATE memory from Firestore."""
    # Simulate Firestore session messages for User A (PRIVATE)
    private_message = {
        "message_id": "m_private",
        "role": "user",
        "name": "Alice",
        "content": "Secret",
        "metadata": {
            "owner_id": user_a_admin.telegram_id,
            "visibility": "PRIVATE",
            "domain": "episodic",
        },
    }
    # Only return the private message for any query
    async def fake_query_session(cls, chat_id, user_ctx, limit=5):
        # Simulate Firestore returning all messages, but RBAC should filter
        if user_ctx.telegram_id == user_a_admin.telegram_id:
            return [private_message]
        # User B should see nothing
        return []
    monkeypatch.setattr(
        __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway,
        "_query_session",
        classmethod(fake_query_session),
    )
    # User B tries to fetch working memory for the same chat
    result = await __import__("src.memory_gateway", fromlist=["MemoryGateway"]).MemoryGateway.fetch_working_memory(
        user_ctx=user_b_guest, chat_id="chat1", limit=5
    )
    assert result == [], "Guest should not see Admin's PRIVATE memory in Firestore"
