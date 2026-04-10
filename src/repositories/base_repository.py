import logging
from typing import Any, Callable, Generic, TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

T = TypeVar("T", bound=SQLModel)
logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Raised when a repository operation fails."""


class BaseRepository(Generic[T]):
    """Generic repository for SQLModel entities.

    This class centralizes database access, transaction management,
    and SQLAlchemy exception handling for the Postgres-backed store.
    """

    def __init__(self, model: type[T], session_factory: Callable[[], AsyncSession]):
        self._model = model
        self._session_factory = session_factory

    async def create(self, payload: dict[str, Any] | T) -> T:
        entity = payload if isinstance(payload, self._model) else self._model(**payload)
        async with self._session_factory() as session:
            try:
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
            except SQLAlchemyError as error:
                await session.rollback()
                logger.error("❌ Repository create failed for %s: %s", self._model.__name__, str(error), exc_info=True)
                raise RepositoryError("Failed to create entity") from error

    async def get_by_id(self, obj_id: Any) -> T | None:
        async with self._session_factory() as session:
            try:
                return await session.get(self._model, obj_id)
            except SQLAlchemyError as error:
                logger.error("❌ Repository get_by_id failed for %s: %s", self._model.__name__, str(error), exc_info=True)
                raise RepositoryError("Failed to retrieve entity by id") from error

    async def update(self, obj_id: Any, updates: dict[str, Any]) -> T | None:
        async with self._session_factory() as session:
            try:
                entity = await session.get(self._model, obj_id)
                if entity is None:
                    return None

                for key, value in updates.items():
                    if hasattr(entity, key):
                        setattr(entity, key, value)

                await session.commit()
                await session.refresh(entity)
                return entity
            except SQLAlchemyError as error:
                await session.rollback()
                logger.error("❌ Repository update failed for %s id=%s: %s", self._model.__name__, obj_id, str(error), exc_info=True)
                raise RepositoryError("Failed to update entity") from error

    async def delete(self, obj_id: Any) -> bool:
        async with self._session_factory() as session:
            try:
                entity = await session.get(self._model, obj_id)
                if entity is None:
                    return False

                await session.delete(entity)
                await session.commit()
                return True
            except SQLAlchemyError as error:
                await session.rollback()
                logger.error("❌ Repository delete failed for %s id=%s: %s", self._model.__name__, obj_id, str(error), exc_info=True)
                raise RepositoryError("Failed to delete entity") from error

    async def filter_by(self, **filters: Any) -> list[T]:
        async with self._session_factory() as session:
            try:
                stmt = select(self._model).filter_by(**filters)
                result = await session.execute(stmt)
                return result.all()
            except SQLAlchemyError as error:
                logger.error("❌ Repository filter_by failed for %s filters=%s: %s", self._model.__name__, filters, str(error), exc_info=True)
                raise RepositoryError("Failed to filter entities") from error

    async def list_all(self) -> list[T]:
        async with self._session_factory() as session:
            try:
                stmt = select(self._model)
                result = await session.execute(stmt)
                return result.all()
            except SQLAlchemyError as error:
                logger.error("❌ Repository list_all failed for %s: %s", self._model.__name__, str(error), exc_info=True)
                raise RepositoryError("Failed to list entities") from error
