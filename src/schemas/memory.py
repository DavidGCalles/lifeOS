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

    def to_chroma_payload(self) -> dict[str, Any]:
        """
        Prepara el objeto para ser insertado en ChromaDB.
        Mueve 'created_at' dentro de metadata para permitir filtrado temporal.
        """
        # Convertimos metadatos a dict plano
        meta_dict = self.metadata.model_dump(exclude_none=True)
        
        # Inyectamos timestamp en metadata para queries temporales en Chroma ($gte, etc)
        meta_dict["created_at"] = self.created_at
        
        return {
            "id": self.id,
            "document": self.content,
            "metadata": meta_dict
        }

    @classmethod
    def from_chroma_result(cls, id: str, document: str, metadata: dict[str, Any]):
        """
        Reconstruye el objeto Pydantic desde la respuesta cruda de ChromaDB.
        """
        # Extraemos created_at que inyectamos al guardar
        created_at = metadata.pop("created_at", datetime.now().isoformat())
        
        # El resto son los metadatos estrictos
        return cls(
            id=id,
            content=document,
            created_at=created_at,
            metadata=EpisodicMemoryMetadata(**metadata)
        )