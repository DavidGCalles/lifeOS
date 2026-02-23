import pytest

from src.tools.memory_tool import RememberTool, RecallTool, ForgetTool
from src.identity_manager import UserContext, UserRole
from src.schemas.memory import (
    EpisodicMemoryItem,
    EpisodicMemoryMetadata,
    MemoryCategory,
    MemoryType,
    MemorySource,
)
from src.memory_gateway import MemoryGateway


@pytest.mark.asyncio
async def test_remember_tool_uses_gateway(monkeypatch):
    tool = RememberTool()
    user = UserContext(telegram_id="u123", name="Test", role=UserRole.FAMILY)
    tool.set_context(user)

    captured = {}

    async def fake_save(ctx, item):
        captured['ctx'] = ctx
        captured['item'] = item
        return "memid"

    monkeypatch.setattr(MemoryGateway, 'save_semantic_memory', fake_save)

    res = await tool._run(content="hello", category=MemoryCategory.FAMILY, type=MemoryType.REFLECTION, tags=None)
    assert "memid" in res
    assert captured['ctx'] is user
    assert captured['item'].metadata.owner_id == "u123"


@pytest.mark.asyncio
async def test_recall_tool_filters_and_context(monkeypatch):
    tool = RecallTool()
    user = UserContext(telegram_id="u456", name="Bob", role=UserRole.EXTERNAL)
    tool.set_context(user)

    dummy_item = EpisodicMemoryItem(
        content="foo",
        metadata=EpisodicMemoryMetadata(
            owner_id="u456",
            category=MemoryCategory.FAMILY,
            type=MemoryType.FACT,
            source=MemorySource.AGENT_REFLECTION,
        ),
    )

    async def fake_search(user_ctx, query, limit=5, domain=None):
        assert user_ctx is user
        return [dummy_item]

    monkeypatch.setattr(MemoryGateway, 'search_semantic_archive', fake_search)

    out = await tool._run(query="anything", category=MemoryCategory.FAMILY.value)
    assert "Found relevant memories" in out
    assert "foo" in out

    # without category should still work
    out2 = await tool._run(query="x")
    assert "Found relevant memories" in out2


@pytest.mark.asyncio
async def test_forget_tool_deletes_via_gateway(monkeypatch):
    tool = ForgetTool()
    user = UserContext(telegram_id="u789", name="Carol", role=UserRole.ADMIN)
    tool.set_context(user)

    dummy_item = EpisodicMemoryItem(
        content="secret",
        metadata=EpisodicMemoryMetadata(
            owner_id="u789",
            category=MemoryCategory.FAMILY,
            type=MemoryType.FACT,
            source=MemorySource.AGENT_REFLECTION,
        ),
    )

    async def fake_search(user_ctx, query, limit=1, domain=None):
        assert user_ctx is user
        return [dummy_item]

    deleted = {}
    async def fake_delete(ctx, mid):
        deleted['id'] = mid

    monkeypatch.setattr(MemoryGateway, 'search_semantic_archive', fake_search)
    monkeypatch.setattr(MemoryGateway, 'delete_semantic_memory', fake_delete)

    res = await tool._run(query="secret")
    assert "DELETED Memory ID" in res
    assert deleted['id'] == dummy_item.id
