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

from src.schemas.db import DBUser, DBTelegramIdentity, UserRole, UserStatus

logger = logging.getLogger(__name__)

class UserContext(BaseModel):
    '''
    Contexto de identidad del usuario, construido a partir de la base de datos.
    '''
    telegram_id: str
    user_id: UUID | None = None
    name: str
    role: UserRole
    status: UserStatus
    description: str | None = None
    profile_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def calendar_id(self) -> str | None:
        '''
        Acceso directo al calendar_id dentro de profile_metadata, si existe.
        '''
        return self.profile_metadata.get("calendar_id")

    @property
    def is_admin(self) -> bool:
        ''' Conveniencia para verificar si el usuario es admin. '''
        return self.role == UserRole.ADMIN


class PostgresIdentityManager:
    ''' Implementación de IdentityManager que resuelve usuarios desde PostgreSQL
    usando SQLModel. '''
    @classmethod
    async def get_user(cls, telegram_id: int | str, session: AsyncSession) -> UserContext:
        ''' Resuelve un usuario a partir de su telegram_id,
        con manejo robusto de errores y casos límite. '''
        tid_str = str(telegram_id)
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
                    role=UserRole.GUEST,
                    status=UserStatus.PENDING,
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
                user_id=db_user.id,
                name=db_user.name,
                role=db_user.role,
                status=db_user.status,
                description=db_user.description,
                profile_metadata=metadata
            )

        except Exception as e:
            logger.error("❌ Error resolving identity for telegram_id=%s: %s",
                         tid_str, str(e), exc_info=True)
            # Default-deny absoluto en caso de fallo de base de datos
            return UserContext(
                telegram_id=tid_str,
                name="ErrorFallback",
                role=UserRole.GUEST,
                status=UserStatus.PENDING,
                description="System Error during resolution"
            )

    @classmethod
    async def register_user(cls, user: UserContext, session: AsyncSession) -> bool:
        """
        Stub de registro. Requerirá instanciar DBUser y DBTelegramIdentity 
        y hacer un session.commit() transaccional.
        """
        logger.warning("🚧 [PG] User registration not yet implemented in" \
        "PostgresIdentityManager.")
        return False
