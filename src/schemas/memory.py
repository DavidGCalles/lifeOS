import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

# --- 1. ENUMS (Restricted Vocabulary) ---

class MemoryCategory(str, Enum):
    PROFESSIONAL = "professional"
    FINANCE = "finance"
    HEALTH = "health"
    FAMILY = "family"
    PERSONAL_DEV = "personal_dev"
    META = "meta"  # Para cosas sobre el propio sistema LifeOS

class MemoryType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference" 
    PLAN = "plan"
    DECISION = "decision" 
    REFLECTION = "reflection"

class MemorySource(str, Enum):
    USER_CHAT = "user_chat"
    AGENT_REFLECTION = "agent_reflection"
    DOCUMENT_IMPORT = "document_import"

# New enums to support the universal RBAC schema (ADR-012)
class MemoryVisibility(str, Enum):
    PRIVATE = "PRIVATE"
    FAMILY = "FAMILY"
    PUBLIC = "PUBLIC"

class MemoryDomainType(str, Enum):
    EPISODIC = "episodic"
    DOCUMENT = "document"
    SYSTEM = "system"

# --- 2. SCHEMAS ---

class BaseMemoryMetadata(BaseModel):
    """Universal metadata that every piece of memory must include.

    Enforced by ADR-012 to guarantee a strict RBAC surface and allow
    vector/domain segregation. All other memory metadata schemas should
    subclass this base model.
    """
    # Telegram ID of the user or system that generated the memory.
    owner_id: str

    # Access control classification for retrieval queries.
    visibility: MemoryVisibility = MemoryVisibility.PRIVATE

    # Semantic domain used to choose the correct storage/index.
    domain: MemoryDomainType


class EpisodicMemoryMetadata(BaseMemoryMetadata):
    """
    Metadata specific to episodic (chat/working) memories.
    Inherits the universal RBAC fields defined above and then adds the
    existing specialized attributes. The original `domain` field has been
    renamed to `category` to avoid confusion with the base `domain` used by
    the memory gateway/Qdrant collection segmentation.
    """
    # override default domain so callers don't have to specify it explicitly
    domain: MemoryDomainType = MemoryDomainType.EPISODIC

    # category of the memory (professional, finance, etc.)
    category: MemoryCategory
    type: MemoryType
    source: MemorySource

    # Campo opcional para trazas extra sin romper el esquema estricto
    context_tags: str | None = None

class EpisodicMemoryItem(BaseModel):
    """
    La unidad atómica de memoria en LifeOS.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: EpisodicMemoryMetadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    created_by: str | None = None
