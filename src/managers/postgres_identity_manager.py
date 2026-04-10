'''
PostgresIdentityManager: Implementación de IdentityManager usando SQLModel y AsyncSession
para PostgreSQL.
'''
import json
import logging
from pydantic import BaseModel
from typing import Any

from src.managers.config_manager import config_manager
from src.repositories.base_repository import BaseRepository, RepositoryError
from src.repositories.identity_repository import IdentityRepository
from src.schemas.db import (
    DBUser,
    DBTelegramIdentity,
    UserRole,
    UserStatus,
)

logger = logging.getLogger(__name__)


class UserContext(BaseModel):
    '''
    Contexto de identidad del usuario, construido a partir de la base de datos.
    '''
    telegram_id: str
    name: str
    role: UserRole
    status: UserStatus
    description: str | None = None
    calendar_id: str | None = None

    @property
    def is_admin(self) -> bool:
        ''' Conveniencia para verificar si el usuario es admin. '''
        return self.role == UserRole.ADMIN


class PostgresIdentityManager:
    ''' Implementación de IdentityManager que resuelve usuarios desde PostgreSQL.

    Este manager delega completamente el acceso a datos a repositorios inyectados.
    '''

    def __init__(self, repository: IdentityRepository):
        self._identity_repository = repository

    def _build_user_context(self, db_user: DBUser, telegram_id: str) -> UserContext:
        metadata = db_user.profile_metadata or {}
        if not isinstance(metadata, dict):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning("⚠️ Failed to parse profile_metadata for user %s", db_user.id)
                metadata = {}

        return UserContext(
            telegram_id=telegram_id,
            name=db_user.name,
            role=db_user.role,
            status=db_user.status,
            description=db_user.description,
            calendar_id=metadata.get("calendar_id"),
        )

    async def get_user(self, telegram_id: int | str) -> UserContext:
        tid_str = str(telegram_id)
        try:
            db_user = await self._identity_repository.get_user_by_telegram_id(telegram_id)
            if db_user is None:
                logger.info("📭 No registered user found for telegram_id=%s", tid_str)
                return UserContext(
                    telegram_id=tid_str,
                    name="Stranger",
                    role=UserRole.GUEST,
                    status=UserStatus.PENDING,
                    description="Unauthorized",
                )
            return self._build_user_context(db_user, tid_str)
        except RepositoryError as error:
            logger.error("❌ Error resolving identity for telegram_id=%s: %s", tid_str, str(error), exc_info=True)
            return UserContext(
                telegram_id=tid_str,
                name="ErrorFallback",
                role=UserRole.GUEST,
                status=UserStatus.PENDING,
                description="System Error during resolution",
            )

    async def register_user(self, user: UserContext) -> bool:
        if await self._identity_repository.has_telegram_identity(user.telegram_id):
            logger.warning("User with telegram_id %s already exists", user.telegram_id)
            return False

        user_payload = {
            "name": user.name,
            "role": user.role,
            "status": UserStatus.APPROVED,
            "description": user.description,
            "profile_metadata": {"calendar_id": user.calendar_id} if user.calendar_id else {},
        }

        try:
            await self._identity_repository.create_user_with_identity(user_payload, user.telegram_id)
            logger.info("✅ User registered successfully: id=%s", user.telegram_id)
            return True
        except RepositoryError as error:
            logger.error("❌ Error registering user %s: %s", user.telegram_id, str(error), exc_info=True)
            return False

    async def update_user(self, telegram_id: int | str, data: dict[str, Any]) -> bool:
        tid_str = str(telegram_id)
        updates: dict[str, Any] = {}

        if "name" in data:
            updates["name"] = data["name"]
        if "role" in data:
            updates["role"] = UserRole(data["role"])
        if "description" in data:
            updates["description"] = data["description"]
        if "calendar_id" in data:
            updates["profile_metadata"] = {"calendar_id": data["calendar_id"]}

        if not updates:
            logger.info("No updatable fields provided for telegram_id=%s", tid_str)
            return False

        try:
            updated_user = await self._identity_repository.update_user_by_telegram_id(telegram_id, updates)
            if updated_user is None:
                logger.warning("User not found for update: %s", tid_str)
                return False
            logger.info("✅ User updated successfully: id=%s", tid_str)
            return True
        except RepositoryError as error:
            logger.error("❌ Error updating user %s: %s", tid_str, str(error), exc_info=True)
            return False

    async def get_user_by_name(self, name: str) -> UserContext | None:
        try:
            db_user = await self._identity_repository.get_user_by_name(name)
            if db_user is None:
                logger.info("No user found for name '%s'", name)
                return None

            telegram_identity = await self._identity_repository.get_telegram_identity_by_user_id(db_user.id)
            if not telegram_identity:
                logger.warning("User %s has no telegram identity", db_user.id)
                return None

            return self._build_user_context(db_user, str(telegram_identity.telegram_id))
        except RepositoryError as error:
            logger.error("Error searching user by name '%s': %s", name, str(error), exc_info=True)
            return None

    async def get_user_by_email(self, email: str) -> UserContext | None:
        try:
            db_user = await self._identity_repository.get_user_by_email(email)
            if db_user is None:
                logger.info("No user found for email '%s'", email)
                return None

            telegram_identity = await self._identity_repository.get_telegram_identity_by_user_id(db_user.id)
            if not telegram_identity:
                logger.warning("User %s has no telegram identity", db_user.id)
                return None

            return self._build_user_context(db_user, str(telegram_identity.telegram_id))
        except RepositoryError as error:
            logger.error("Error searching user by email '%s': %s", email, str(error), exc_info=True)
            return None

    async def get_users_by_role(self, role: UserRole) -> list[UserContext]:
        try:
            db_users = await self._identity_repository.get_users_by_role(role)
            users: list[UserContext] = []
            for db_user in db_users:
                telegram_identity = await self._identity_repository.get_telegram_identity_by_user_id(db_user.id)
                if not telegram_identity:
                    continue
                users.append(self._build_user_context(db_user, str(telegram_identity.telegram_id)))
            logger.info("Found %d users with role '%s'", len(users), role)
            return users
        except RepositoryError as error:
            logger.error("Error searching users by role '%s': %s", role, str(error), exc_info=True)
            return []


# Default instance for application wiring.
user_repository = BaseRepository(DBUser, config_manager.get_async_session)
telegram_repository = BaseRepository(DBTelegramIdentity, config_manager.get_async_session)
identity_repository = IdentityRepository(user_repository, telegram_repository)
identity_manager = PostgresIdentityManager(identity_repository)

# Convenience export for legacy import patterns.
IdentityManager = identity_manager
