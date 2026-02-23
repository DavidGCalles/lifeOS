import asyncio
from typing import Any, Dict, List, Optional, Union

from google.cloud.firestore import Query
from qdrant_client import models

from src.identity_manager import UserContext, UserRole
from src.schemas.memory import MemoryVisibility, EpisodicMemoryItem
from src.utils.session_manager import SessionManager
from src.memory_manager import VectorMemoryManager


class MemoryGateway:
    """Centralized access layer for all memory reads.

    Agents and orchestrators must never interact with Firestore or Qdrant
    directly; this class acts as a **zero‑trust proxy** that injects
    mathematically enforceable RBAC filters based on a provided
    :class:`UserContext`.

    The gateway exposes **isolated channels** for each underlying storage
    engine instead of performing any cross-engine merging or summarization.
    Every public-facing operation **requires** a non-null ``UserContext``
    instance; failing to supply one will raise a ``ValueError``.
    """

    @staticmethod
    def _build_rbac_filter(user_ctx: UserContext) -> models.Filter:
        """Create a Qdrant ``Filter`` representing the OR visibility rules.

        The universal RBAC policy is encoded as a set of ``should`` conditions:

        * owner_id == query_user_id
        * visibility == PUBLIC
        * visibility == FAMILY (only if the querying role is FAMILY or ADMIN)

        By using ``should`` we allow the vector engine to return any point that
        satisfies at least one of the clauses.  This is the mathematical
        enforcement described in ADR-012.
        """
        owner_cond = models.FieldCondition(
            key="owner_id",
            match=models.MatchValue(value=user_ctx.telegram_id),
        )
        public_cond = models.FieldCondition(
            key="visibility",
            match=models.MatchValue(value=MemoryVisibility.PUBLIC.value),
        )

        conditions: List[models.FieldCondition] = [owner_cond, public_cond]
        if user_ctx.role in (UserRole.FAMILY, UserRole.ADMIN):
            family_cond = models.FieldCondition(
                key="visibility",
                match=models.MatchValue(value=MemoryVisibility.FAMILY.value),
            )
            conditions.append(family_cond)

        return models.Filter(should=conditions)

    @classmethod
    async def _query_vector(
        cls,
        query: str,
        user_ctx: UserContext,
        domain: Optional[str] = None,
        limit: int = 5,
    ) -> List[EpisodicMemoryItem]:
        """Search semantic memory with RBAC filters applied.

        Under the hood we delegate to :class:`VectorMemoryManager`, but we
        supply a pre-built ``models.Filter`` so that ownership/visibility
        restrictions cannot be bypassed.
        """
        manager = VectorMemoryManager(domain=domain)
        rbac = cls._build_rbac_filter(user_ctx)
        return await manager.search_memory(query=query, filters=rbac, limit=limit)

    @classmethod
    async def _query_session(
        cls,
        chat_id: Union[str, int],
        user_ctx: UserContext,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Retrieve session messages that the caller is allowed to see.

        We intentionally issue multiple Firestore ``where`` queries and then
        deduplicate them rather than falling back to a single unfiltered scan.
        This satisfies the requirement of "injecting Firestore where clauses."  
        """
        db = SessionManager._get_db()
        if not db:
            return []

        cid = str(chat_id)
        base = (
            db.collection("sessions")
            .document(cid)
            .collection("messages")
            .order_by("timestamp", direction=Query.DESCENDING)
        )

        queries = []
        # owner-specific turn
        queries.append(base.where("metadata.owner_id", "==", user_ctx.telegram_id))
        # public turns
        queries.append(base.where("metadata.visibility", "==", MemoryVisibility.PUBLIC.value))
        # "family" turns are only readable by FAMILY/ADMIN
        if user_ctx.role in (UserRole.FAMILY, UserRole.ADMIN):
            queries.append(
                base.where("metadata.visibility", "==", MemoryVisibility.FAMILY.value)
            )

        messages: List[Dict[str, Any]] = []
        seen_ids: set = set()
        for q in queries:
            async for doc in q.limit(limit).stream():
                data = doc.to_dict()
                mid = str(data.get("message_id", ""))
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)

                messages.append(
                    {
                        "message_id": data.get("message_id"),
                        "role": data.get("role"),
                        "name": data.get("name"),
                        "content": data.get("content"),
                        "metadata": {
                            "owner_id": data.get("owner_id")
                            or data.get("metadata", {}).get("owner_id"),
                            "visibility": data.get("visibility")
                            or data.get("metadata", {}).get("visibility"),
                            "domain": data.get("domain")
                            or data.get("metadata", {}).get("domain"),
                        },
                    }
                )

        # The original SessionManager returned results oldest-first by
        # reversing the list; we do the same here for compatibility.
        return messages[::-1]


    # ------------------------------------------------------------------
    # Public isolated channels
    # ------------------------------------------------------------------

    @classmethod
    async def fetch_working_memory(
        cls,
        user_ctx: UserContext,
        chat_id: Union[str, int],
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Return Firestore session messages visible to ``user_ctx``.

        This method does not perform any federation or merging.  It simply
        validates the context and delegates to ``_query_session``.
        """
        if not user_ctx:
            raise ValueError("UserContext must be provided for every read operation")
        return await cls._query_session(chat_id, user_ctx, limit=limit)

    @classmethod
    async def search_semantic_archive(
        cls,
        user_ctx: UserContext,
        query: str,
        limit: int = 5,
        domain: Optional[str] = None,
    ) -> List[EpisodicMemoryItem]:
        """Run a semantic vector search with RBAC filters applied.

        Again, this is a thin wrapper around ``_query_vector`` and will not
        mix results from Firestore.
        """
        if not user_ctx:
            raise ValueError("UserContext must be provided for every read operation")
        return await cls._query_vector(query, user_ctx, domain=domain, limit=limit)
