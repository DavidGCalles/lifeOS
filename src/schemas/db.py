import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Any

from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import JSONB

# Importamos los Enums compartidos con el dominio vectorial para no duplicar la fuente de la verdad
from src.schemas.memory import MemoryVisibility, MemoryDomainType


# ==============================================================================
# 1. ENUMS ESTRICTOS DE BASE DE DATOS
# ==============================================================================
class UserRole(str, PyEnum):
    ADMIN = "ADMIN"
    FAMILY = "FAMILY"
    EXTERNAL = "EXTERNAL"
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    GUEST = "GUEST"

class UserStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    BANNED = "BANNED"

class SessionStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

class TaskStatus(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

def utc_now():
    return datetime.now(timezone.utc)


# ==============================================================================
# 2. MODELOS RELACIONALES (Tablas)
# ==============================================================================

class DBUser(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    role: UserRole = Field(default=UserRole.GUEST)
    status: UserStatus = Field(default=UserStatus.PENDING)
    
    name: str = Field(default="Unknown", sa_column=Column(String(255)))
    description: str | None = Field(default=None)
    profile_metadata: dict[str, Any] = Field(
        default_factory=dict, 
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    )

    created_at: datetime = Field(default_factory=utc_now)

    # Relaciones inversas
    telegram_identities: list["DBTelegramIdentity"] = Relationship(back_populates="user", cascade_delete=True)
    sessions: list["DBSession"] = Relationship(back_populates="user", cascade_delete=True)
    messages: list["DBMessage"] = Relationship(back_populates="owner", cascade_delete=True)


class DBTelegramIdentity(SQLModel, table=True):
    __tablename__ = "telegram_identities"

    telegram_id: int = Field(primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)

    user: DBUser = Relationship(back_populates="telegram_identities")


class DBSession(SQLModel, table=True):
    __tablename__ = "sessions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    user: DBUser = Relationship(back_populates="sessions")
    tasks: list["DBTask"] = Relationship(back_populates="session", cascade_delete=True)
    messages: list["DBMessage"] = Relationship(back_populates="session", cascade_delete=True)


class DBTask(SQLModel, table=True):
    __tablename__ = "tasks"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="sessions.id", index=True)
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)
    
    # Forzamos JSONB nativo de Postgres para el payload de los workers
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    session: DBSession = Relationship(back_populates="tasks")


class DBMessage(SQLModel, table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="sessions.id", index=True)
    
    # Campos aplanados del mensaje
    role: str = Field(sa_column=Column(String(50), nullable=False))
    content: str = Field(nullable=False)
    name: str | None = Field(default=None, sa_column=Column(String(255)))
    input_type: str = Field(sa_column=Column(String(50), nullable=False))
    agent_key: str | None = Field(default=None, sa_column=Column(String(255)))
    consolidated: bool = Field(default=False)
    
    # Metadatos del RBAC aplanados (Tu muro de contención)
    owner_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    visibility: MemoryVisibility = Field(default=MemoryVisibility.PRIVATE)
    domain: MemoryDomainType = Field(default=MemoryDomainType.EPISODIC)
    
    created_at: datetime = Field(default_factory=utc_now)

    session: DBSession = Relationship(back_populates="messages")
    owner: DBUser = Relationship(back_populates="messages")