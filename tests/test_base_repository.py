import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from sqlmodel import SQLModel, Field

# ensure src is on path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.base_repository import BaseRepository


class FakeModel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


@pytest.mark.asyncio
async def test_base_repository_create_commits_and_refreshes():
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()

    session_factory = MagicMock(return_value=mock_session)
    repo = BaseRepository(FakeModel, session_factory)

    result = await repo.create({"name": "Alice"})

    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()
    assert isinstance(result, FakeModel)
    assert result.name == "Alice"


@pytest.mark.asyncio
async def test_base_repository_get_by_id_returns_entity():
    entity = FakeModel(id=1, name="Bob")
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=entity)

    session_factory = MagicMock(return_value=mock_session)
    repo = BaseRepository(FakeModel, session_factory)

    result = await repo.get_by_id(1)

    mock_session.get.assert_awaited_once_with(FakeModel, 1)
    assert result is entity


@pytest.mark.asyncio
async def test_base_repository_update_commits_and_refreshes():
    entity = FakeModel(id=2, name="Carol")
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=entity)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    session_factory = MagicMock(return_value=mock_session)
    repo = BaseRepository(FakeModel, session_factory)

    result = await repo.update(2, {"name": "Dan"})

    mock_session.get.assert_awaited_once_with(FakeModel, 2)
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(entity)
    assert result.name == "Dan"


@pytest.mark.asyncio
async def test_base_repository_delete_returns_true_when_entity_found():
    entity = FakeModel(id=3, name="Eve")
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock(return_value=entity)
    mock_session.delete = AsyncMock()
    mock_session.commit = AsyncMock()

    session_factory = MagicMock(return_value=mock_session)
    repo = BaseRepository(FakeModel, session_factory)

    result = await repo.delete(3)

    mock_session.delete.assert_awaited_once_with(entity)
    mock_session.commit.assert_awaited_once()
    assert result is True


@pytest.mark.asyncio
async def test_base_repository_filter_by_returns_matching_entities():
    entity = FakeModel(id=4, name="Frank")
    mock_result = MagicMock()
    mock_result.all.return_value = [entity]

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.exec = AsyncMock(return_value=mock_result)

    session_factory = MagicMock(return_value=mock_session)
    repo = BaseRepository(FakeModel, session_factory)

    result = await repo.filter_by(name="Frank")

    mock_session.exec.assert_awaited_once()
    assert result == [entity]
