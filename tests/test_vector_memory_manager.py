import pytest
import asyncio
from pydantic import ValidationError

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.managers.memory_manager import VectorMemoryManager
from src.schemas.memory import (
    MemoryDomainType,
    EpisodicMemoryItem,
    EpisodicMemoryMetadata,
    BaseMemoryMetadata,
)


class DummyClient:
    def __init__(self):
        self.upsert_called = False
        self.last_args = None

    async def upsert(self, collection_name, points, wait):
        self.upsert_called = True
        self.last_args = (collection_name, points, wait)

    async def get_collection(self, collection_name):
        # always raise so that _ensure_collection will attempt to create the
        # collection and we can observe the call
        raise Exception("not found")

    async def create_collection(self, collection_name, vectors_config):
        # record if someone asks to create
        if not hasattr(self, "created"):
            self.created = []
        self.created.append(collection_name)

    async def create_payload_index(self, **kwargs):
        # ignore
        pass


@pytest.fixture(autouse=True)
def disable_network(monkeypatch):
    """Prevent real Qdrant connections and embeddings during all tests."""
    async def dummy_init(self):
        if self._client is None:
            self._client = DummyClient()
    monkeypatch.setattr(VectorMemoryManager, "_initialize_client", dummy_init)
    async def fake_embed(self, text: str):
        return [0.0] * 384
    monkeypatch.setattr(VectorMemoryManager, "_get_embedding", fake_embed)


@pytest.mark.asyncio
async def test_domain_collection_mapping():
    m = VectorMemoryManager(domain=MemoryDomainType.DOCUMENT)
    assert m._collection_name == "mem_documents"

    m2 = VectorMemoryManager(domain="system")
    assert m2._collection_name == "mem_system"

    # old style remains allowed
    m3 = VectorMemoryManager(collection_name="custom")
    assert m3._collection_name == "custom"


@pytest.mark.asyncio
async def test_add_memory_enforces_base_schema(monkeypatch):
    manager = VectorMemoryManager(domain=MemoryDomainType.EPISODIC)
    dummy = DummyClient()
    manager._client = dummy
    async def mock_get_embedding(*args, **kwargs):
        return [0.0] * 384
    monkeypatch.setattr(VectorMemoryManager, "_get_embedding", mock_get_embedding)
    # build a valid episodic memory
    mem = EpisodicMemoryItem(
        content="hello",
        metadata=EpisodicMemoryMetadata(
            owner_id="u1",
            category="professional",
            type="fact",
            source="user_chat",
        ),
        created_by="tester",
    )

    mid = await manager.add_memory(mem)
    assert mid == mem.id
    assert dummy.upsert_called
    coll, points, wait = dummy.last_args
    assert coll == "mem_episodic"
    # payload must at least include the base metadata keys
    payload = points[0].payload
    for key in ("owner_id", "visibility", "domain"):
        assert key in payload
    # domain-specific fields should still be preserved
    assert payload.get("category") == "professional"
    assert payload.get("type") == "fact"


@pytest.mark.asyncio
async def test_add_memory_allows_extra_metadata_keys():
    manager = VectorMemoryManager(domain=MemoryDomainType.EPISODIC)
    dummy = DummyClient()
    manager._client = dummy

    # subclass the episodic-specific metadata so Pydantic validation inside
    # EpisodicMemoryItem accepts it
    class ExoticEpisodic(EpisodicMemoryMetadata):
        extra: str

    exotic = ExoticEpisodic(
        owner_id="u2",
        category="professional",
        type="fact",
        source="user_chat",
        extra="yay",
    )
    item = EpisodicMemoryItem(content="weird", metadata=exotic)

    await manager.add_memory(item)
    assert dummy.upsert_called
    payload = dummy.last_args[1][0].payload
    assert payload["extra"] == "yay"


@pytest.mark.asyncio
async def test_ensure_all_collections_creates_domains(monkeypatch):
    manager = VectorMemoryManager(domain=MemoryDomainType.SYSTEM)
    dummy = DummyClient()
    manager._client = dummy

    await manager._ensure_all_collections()
    # ensure that the expected three collections were created
    assert set(dummy.created) == {"mem_episodic", "mem_documents", "mem_system"}
