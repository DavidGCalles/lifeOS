import logging
from sqlmodel import select
from typing import Any

from src.repositories.base_repository import BaseRepository, RepositoryError
from src.schemas.db import DBUser, DBTelegramIdentity, UserRole

logger = logging.getLogger(__name__)


class IdentityRepository:
    """Repository that exposes identity-specific queries for Postgres."""

    def __init__(self, user_repo: BaseRepository[DBUser], telegram_repo: BaseRepository[DBTelegramIdentity]):
        self._user_repo = user_repo
        self._telegram_repo = telegram_repo
        self._session_factory = user_repo._session_factory

    async def get_user_by_telegram_id(self, telegram_id: int | str) -> DBUser | None:
        async with self._session_factory() as session:
            try:
                stmt = (
                    select(DBUser)
                    .join(DBTelegramIdentity, DBUser.id == DBTelegramIdentity.user_id)
                    .where(DBTelegramIdentity.telegram_id == int(telegram_id))
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception as error:
                logger.error("❌ IdentityRepository get_user_by_telegram_id failed: %s", str(error), exc_info=True)
                raise RepositoryError("Failed to query user by telegram id") from error

    async def get_user_by_name(self, name: str) -> DBUser | None:
        async with self._session_factory() as session:
            try:
                stmt = select(DBUser).where(getattr(DBUser, "name").ilike(name))  # type: ignore[attr-defined]
                result = await session.execute(stmt)
                return result.first()
            except Exception as error:
                logger.error("❌ IdentityRepository get_user_by_name failed: %s", str(error), exc_info=True)
                raise RepositoryError("Failed to query user by name") from error

    async def get_user_by_email(self, email: str) -> DBUser | None:
        normalized_email = email.strip().lower()
        async with self._session_factory() as session:
            try:
                stmt = select(DBUser).where(getattr(DBUser, "profile_metadata").contains({"calendar_id": normalized_email}))  # type: ignore[attr-defined]
                result = await session.execute(stmt)
                return result.first()
            except Exception as error:
                logger.error("❌ IdentityRepository get_user_by_email failed: %s", str(error), exc_info=True)
                raise RepositoryError("Failed to query user by email") from error

    async def get_users_by_role(self, role: UserRole) -> list[DBUser]:
        async with self._session_factory() as session:
            try:
                stmt = select(DBUser).where(DBUser.role == role)
                result = await session.execute(stmt)
                return result.all()
            except Exception as error:
                logger.error("❌ IdentityRepository get_users_by_role failed: %s", str(error), exc_info=True)
                raise RepositoryError("Failed to query users by role") from error

    async def has_telegram_identity(self, telegram_id: int | str) -> bool:
        matches = await self._telegram_repo.filter_by(telegram_id=int(telegram_id))
        return len(matches) > 0

    async def get_telegram_identity_by_user_id(self, user_id: Any) -> DBTelegramIdentity | None:
        matches = await self._telegram_repo.filter_by(user_id=user_id)
        return matches[0] if matches else None

    async def create_user_with_identity(self, user_data: dict[str, Any], telegram_id: int | str) -> DBUser:
        async with self._session_factory() as session:
            try:
                if await self.has_telegram_identity(telegram_id):
                    raise RepositoryError("Telegram identity already exists")

                db_user = DBUser(**user_data)
                session.add(db_user)
                await session.flush()

                telegram_identity = DBTelegramIdentity(
                    telegram_id=int(telegram_id),
                    user_id=db_user.id,
                )
                session.add(telegram_identity)
                await session.commit()
                await session.refresh(db_user)
                return db_user
            except Exception as error:
                await session.rollback()
                logger.error("❌ IdentityRepository create_user_with_identity failed: %s", str(error), exc_info=True)
                raise RepositoryError("Failed to create user and identity") from error

    async def update_user_by_telegram_id(self, telegram_id: int | str, updates: dict[str, Any]) -> DBUser | None:
        async with self._session_factory() as session:
            try:
                stmt = (
                    select(DBUser)
                    .join(DBTelegramIdentity, DBUser.id == DBTelegramIdentity.user_id)
                    .where(DBTelegramIdentity.telegram_id == int(telegram_id))
                )
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                if user is None:
                    return None

                for key, value in updates.items():
                    if hasattr(user, key):
                        setattr(user, key, value)

                await session.commit()
                await session.refresh(user)
                return user
            except Exception as error:
                await session.rollback()
                logger.error("❌ IdentityRepository update_user_by_telegram_id failed: %s", str(error), exc_info=True)
                raise RepositoryError("Failed to update user by telegram id") from error
