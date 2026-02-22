import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from pydantic import ValidationError

from src.schemas.memory import (
    BaseMemoryMetadata,
    EpisodicMemoryMetadata,
    MemoryCategory,
    MemoryDomainType,
    MemoryVisibility,
    MemoryType,
    MemorySource,
)


def test_base_metadata_instantiation():
    # Base model can be created directly but requires its mandatory fields.
    bm = BaseMemoryMetadata(owner_id="u123", domain=MemoryDomainType.SYSTEM)
    assert bm.owner_id == "u123"
    assert bm.visibility == MemoryVisibility.PRIVATE
    assert bm.domain == MemoryDomainType.SYSTEM


def test_episodic_metadata_defaults_and_inheritance():
    # When creating episode metadata, domain should default to EPISODIC
    em = EpisodicMemoryMetadata(
        owner_id="user42",
        category=MemoryCategory.FINANCE,
        type=MemoryType.FACT,
        source=MemorySource.USER_CHAT,
    )
    assert isinstance(em, BaseMemoryMetadata)
    assert em.domain == MemoryDomainType.EPISODIC
    assert em.visibility == MemoryVisibility.PRIVATE
    assert em.category == MemoryCategory.FINANCE


def test_missing_owner_id_raises():
    with pytest.raises(ValidationError):
        EpisodicMemoryMetadata(
            category=MemoryCategory.HEALTH,
            type=MemoryType.PREFERENCE,
            source=MemorySource.DOCUMENT_IMPORT,
        )


def test_invalid_category_raises():
    with pytest.raises(ValidationError):
        # Supply a string not in the enum
        EpisodicMemoryMetadata(
            owner_id="u",
            category="foobar",  # type: ignore[arg-type]
            type=MemoryType.PLAN,
            source=MemorySource.USER_CHAT,
        )


def test_serialization_contains_all_fields():
    em = EpisodicMemoryMetadata(
        owner_id="u9",
        category=MemoryCategory.META,
        type=MemoryType.DECISION,
        source=MemorySource.AGENT_REFLECTION,
    )
    d = em.model_dump()
    # check base keys
    for key in ("owner_id", "visibility", "domain", "category", "type", "source"):
        assert key in d
