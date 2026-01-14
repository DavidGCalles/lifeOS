import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

# --- 1. ENUMS (Restricted Vocabulary) ---

class MemoryDomain(str, Enum):
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

# --- 2. SCHEMAS ---

class EpisodicMemoryMetadata(BaseModel):
    """
    Define estrictamente qué metadatos aceptamos.
    Esto evita que un agente invente campos como 'mood' o 'category'.
    """
    domain: MemoryDomain
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
