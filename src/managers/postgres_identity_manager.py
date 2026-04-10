'''
PostgresIdentityManager: Implementación de IdentityManager usando SQLModel y AsyncSession
para PostgreSQL.
'''
import logging
from typing import Any
from uuid import UUID
import json
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.managers.config_manager import config_manager

logger = logging.getLogger(__name__)

class UserContext(BaseModel):
    '''
    Contexto de identidad del usuario, construido a partir de la base de datos.
    '''
    telegram_id: str
    name: str
    role: UserRole
    description: str | None = None
    calendar_id: str | None = None

    @property
    def is_admin(self) -> bool:
        ''' Conveniencia para verificar si el usuario es admin. '''
        return self.role == UserRole.ADMIN


class PostgresIdentityManager:
    ''' Implementación de IdentityManager que resuelve usuarios desde PostgreSQL
    usando SQLModel. '''
    @classmethod
    async def get_user(cls, telegram_id: int | str) -> UserContext:
        ''' Resuelve un usuario a partir de su telegram_id,
        con manejo robusto de errores y casos límite. '''
        tid_str = str(telegram_id)
        async with config_manager.get_async_session() as session:
            try:
                stmt = (
                    select(DBUser)
                    .join(DBTelegramIdentity, DBUser.id == DBTelegramIdentity.user_id)
                    .where(DBTelegramIdentity.telegram_id == int(telegram_id))
                )
                result = await session.exec(stmt)
                db_user = result.scalar_one_or_none()

                # 2. Manejo de desconocido (Stranger)
                if not db_user:
                    logger.info("📭 No registered user found for telegram_id=%s", tid_str)
                    return UserContext(
                        telegram_id=tid_str,
                        name="Stranger",
                        role=UserRole.PENDING,
                        description="Unauthorized"
                    )

                # 3. Parseo defensivo del JSONB
                # asyncpg devuelve dict nativo para JSONB, pero cubrimos la espalda.
                metadata = db_user.profile_metadata or {}
                if not isinstance(metadata, dict):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        logger.warning("⚠️ Failed to parse profile_metadata for user %s", db_user.id)
                        metadata = {}

                # 4. Retorno del Contexto Limpio
                return UserContext(
                    telegram_id=tid_str,
                    name=db_user.name,
                    role=db_user.role,
                    description=db_user.description,
                    calendar_id=metadata.get("calendar_id")
                )

            except Exception as e:
                logger.error("❌ Error resolving identity for telegram_id=%s: %s",
                             tid_str, str(e), exc_info=True)
                # Default-deny absoluto en caso de fallo de base de datos
                return UserContext(
                    telegram_id=tid_str,
                    name="ErrorFallback",
                    role=UserRole.PENDING,
                    description="System Error during resolution"
                )

    @classmethod
    async def register_user(cls, user: UserContext) -> bool:
        """
        Registra un usuario nuevo en PostgreSQL usando SQLModel.
        """
        async with config_manager.get_async_session() as session:
            try:
                # Check if user already exists
                existing_stmt = (
                    select(DBTelegramIdentity)
                    .where(DBTelegramIdentity.telegram_id == int(user.telegram_id))
                )
                result = await session.exec(existing_stmt)
                if result.scalar_one_or_none():
                    logger.warning("User with telegram_id %s already exists", user.telegram_id)
                    return False

                # Create DBUser
                db_user = DBUser(
                    name=user.name,
                    role=user.role,
                    status=UserStatus.APPROVED,  # Assuming registration approves
                    description=user.description,
                    profile_metadata={"calendar_id": user.calendar_id} if user.calendar_id else {}
                )
                session.add(db_user)
                await session.flush()  # To get the id

                # Create DBTelegramIdentity
                telegram_identity = DBTelegramIdentity(
                    telegram_id=int(user.telegram_id),
                    user_id=db_user.id
                )
                session.add(telegram_identity)

                await session.commit()
                logger.info("✅ User registered successfully: id=%s", user.telegram_id)
                return True
            except Exception as e:
                await session.rollback()
                logger.error("❌ Error registering user %s: %s", user.telegram_id, str(e), exc_info=True)
                return False

    @classmethod
    async def update_user(cls, telegram_id: int | str, data: dict) -> bool:
        tid_str = str(telegram_id)
        
        logger.debug("🔄 User update initiated: telegram_id=%s fields=%s", tid_str, list(data.keys()))
        
        async with config_manager.get_async_session() as session:
            try:
                # Find the user
                stmt = (
                    select(DBUser)
                    .join(DBTelegramIdentity, DBUser.id == DBTelegramIdentity.user_id)
                    .where(DBTelegramIdentity.telegram_id == int(telegram_id))
                )
                result = await session.exec(stmt)
                db_user = result.scalar_one_or_none()
                
                if not db_user:
                    logger.warning("User not found for update: %s", tid_str)
                    return False

                # Update fields
                if 'name' in data:
                    db_user.name = data['name']
                if 'role' in data:
                    db_user.role = UserRole(data['role'])
                if 'description' in data:
                    db_user.description = data['description']
                if 'calendar_id' in data:
                    metadata = db_user.profile_metadata or {}
                    metadata['calendar_id'] = data['calendar_id']
                    db_user.profile_metadata = metadata

                await session.commit()
                logger.info("✅ User updated successfully: id=%s", tid_str)
                return True
            except Exception as e:
                await session.rollback()
                logger.error("❌ Error updating user %s: %s", tid_str, str(e), exc_info=True)
                return False

    @classmethod
    async def get_user_by_name(cls, name: str) -> UserContext | None:
        """
        Intenta encontrar un UserContext por nombre.
        """
        logger.debug("🔍 User lookup by name: name='%s'", name)
        
        normalized_name = name.strip().lower()

        async with config_manager.get_async_session() as session:
            try:
                stmt = select(DBUser).where(DBUser.name.ilike(name))
                result = await session.exec(stmt)
                db_user = result.first()
                
                if not db_user:
                    logger.info("No user found for name '%s'", name)
                    return None

                # Get telegram_id
                telegram_stmt = select(DBTelegramIdentity).where(DBTelegramIdentity.user_id == db_user.id)
                telegram_result = await session.exec(telegram_stmt)
                telegram_identity = telegram_result.first()
                
                if not telegram_identity:
                    logger.warning("User %s has no telegram identity", db_user.id)
                    return None

                metadata = db_user.profile_metadata or {}
                return UserContext(
                    telegram_id=str(telegram_identity.telegram_id),
                    name=db_user.name,
                    role=db_user.role,
                    description=db_user.description,
                    calendar_id=metadata.get("calendar_id")
                )
            except Exception as e:
                logger.error("Error searching user by name '%s': %s", name, str(e))
                return None

    @classmethod
    async def get_user_by_email(cls, email: str) -> UserContext | None:
        """
        Search for a user by their calendar_id (email).
        """
        normalized_email = email.strip().lower()
        logger.debug("🔍 User lookup by email: email='%s'", normalized_email)

        async with config_manager.get_async_session() as session:
            try:
                # Search in profile_metadata for calendar_id
                stmt = select(DBUser).where(DBUser.profile_metadata.contains({"calendar_id": normalized_email}))
                result = await session.exec(stmt)
                db_user = result.first()
                
                if not db_user:
                    logger.info("No user found for email '%s'", normalized_email)
                    return None

                # Get telegram_id
                telegram_stmt = select(DBTelegramIdentity).where(DBTelegramIdentity.user_id == db_user.id)
                telegram_result = await session.exec(telegram_stmt)
                telegram_identity = telegram_result.first()
                
                if not telegram_identity:
                    logger.warning("User %s has no telegram identity", db_user.id)
                    return None

                metadata = db_user.profile_metadata or {}
                return UserContext(
                    telegram_id=str(telegram_identity.telegram_id),
                    name=db_user.name,
                    role=db_user.role,
                    description=db_user.description,
                    calendar_id=metadata.get("calendar_id")
                )
            except Exception as e:
                logger.error("Error searching user by email '%s': %s", normalized_email, str(e))
                return None

    @classmethod
    async def get_users_by_role(cls, role: UserRole) -> list[UserContext]:
        """
        Retrieves all users with a specific role.
        """
        logger.debug("🔍 User lookup by role: role='%s'", role)
        users = []
        
        async with config_manager.get_async_session() as session:
            try:
                stmt = select(DBUser).where(DBUser.role == role)
                result = await session.exec(stmt)
                db_users = result.all()
                
                for db_user in db_users:
                    # Get telegram_id
                    telegram_stmt = select(DBTelegramIdentity).where(DBTelegramIdentity.user_id == db_user.id)
                    telegram_result = await session.exec(telegram_stmt)
                    telegram_identity = telegram_result.first()
                    
                    if telegram_identity:
                        metadata = db_user.profile_metadata or {}
                        users.append(UserContext(
                            telegram_id=str(telegram_identity.telegram_id),
                            name=db_user.name,
                            role=db_user.role,
                            description=db_user.description,
                            calendar_id=metadata.get("calendar_id")
                        ))
                
                logger.info("Found %d users with role '%s'", len(users), role)
                return users
            except Exception as e:
                logger.error("Error searching users by role '%s': %s", role, str(e))
                return []
