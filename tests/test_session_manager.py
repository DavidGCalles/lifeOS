import os
import sys
import pytest

# ensure src is on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError

from src.schemas.memory import MemoryVisibility, MemoryDomainType, SessionMessage
from src.utils.session_manager import SessionManager


@pytest.mark.asyncio
async def test_add_message_validates_and_returns_object(monkeypatch):
    # disable Firestore so no network calls are attempted
    monkeypatch.setenv("USE_FIRESTORE", "False")

    payload = {
        "message_id": 75,
        "role": "user",
        "content": "hello world",
        "user_id": 1234,
        "name": "TestUser",
        "input_type": "text",
    }

    result = await SessionManager.add_message(chat_id=1, message_data=payload)
    assert isinstance(result, SessionMessage)
    # the helper converts the id to a string
    assert result.metadata.owner_id == str(payload["user_id"])
    # default visibility should be PRIVATE when not provided
    assert result.metadata.visibility == MemoryVisibility.PRIVATE
    # default domain is episodic
    assert result.metadata.domain == MemoryDomainType.EPISODIC


@pytest.mark.asyncio
async def test_add_message_respects_explicit_visibility(monkeypatch):
    monkeypatch.setenv("USE_FIRESTORE", "False")

    payload = {
        "role": "bot",
        "content": "system update",
        "user_id": 55,
        "name": "Server",
        "input_type": "text",
        "visibility": MemoryVisibility.FAMILY,
    }

    result = await SessionManager.add_message(chat_id=2, message_data=payload)
    # equality works whether the field comes back as an enum or a string
    assert result.metadata.visibility == MemoryVisibility.FAMILY
    assert result.metadata.owner_id == str(payload["user_id"])


@pytest.mark.asyncio
async def test_add_message_missing_required_fields_raises(monkeypatch):
    monkeypatch.setenv("USE_FIRESTORE", "False")

    # missing role/content should trigger validation error
    bad_payload = {"user_id": 999}
    with pytest.raises(ValidationError):
        await SessionManager.add_message(chat_id=3, message_data=bad_payload)


@pytest.mark.asyncio
async def test_get_context_includes_metadata(monkeypatch):
    # Construct a fake Firestore-like client that returns a single message
    sample = {
        "message_id": 10,
        "role": "user",
        "content": "foo",
        "name": "Bar",
        "owner_id": "55",
        "visibility": "PRIVATE",
        "domain": "episodic",
    }

    class FakeDoc:
        def __init__(self, data):
            self._data = data

        def to_dict(self):
            return self._data

    class FakeStream:
        def __init__(self, docs):
            self._iter = iter(docs)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return FakeDoc(next(self._iter))
            except StopIteration:
                raise StopAsyncIteration

    class FakeMessages:
        def __init__(self, docs):
            self.docs = docs

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, n):
            return self

        def stream(self):
            return FakeStream(self.docs)

    class FakeSession:
        def __init__(self, docs):
            self.docs = docs

        def collection(self, name):
            if name == "messages":
                return FakeMessages(self.docs)
            raise KeyError

    class FakeDB:
        def __init__(self, store):
            self.store = store

        def collection(self, name):
            if name == "sessions":

                class Inner:
                    def __init__(self, store):
                        self.store = store

                    def document(self, cid):
                        return FakeSession(self.store.get(cid, []))

                return Inner(self.store)
            raise KeyError

    fake = FakeDB({"100": [sample]})
    monkeypatch.setattr(SessionManager, "_get_db", classmethod(lambda cls: fake))

    result = await SessionManager.get_context(chat_id=100, limit=5)
    assert result and isinstance(result[0], dict)
    assert result[0]["metadata"]["owner_id"] == "55"
    assert result[0]["metadata"]["visibility"] == "PRIVATE"
    assert result[0]["metadata"]["domain"] == MemoryDomainType.EPISODIC.value
