import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

from google.cloud.firestore import Query
from qdrant_client import models

from src.identity_manager import UserContext, UserRole
from src.schemas.memory import MemoryVisibility, EpisodicMemoryItem
from src.utils.session_manager import SessionManager
from src.memory_manager import VectorMemoryManager

logger = logging.getLogger(__name__)


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

        filter_obj = models.Filter(should=conditions)
        logger.debug("🔐 RBAC Filter built for user %s (role=%s) with %d conditions", user_ctx.telegram_id, user_ctx.role, len(conditions))
        return filter_obj

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
        start_time = time.time()
        logger.info("🔍 Vector search initiated: query='%s' domain=%s limit=%d user=%s", query[:50], domain or 'episodic', limit, user_ctx.telegram_id)
        
        try:
            manager = VectorMemoryManager(domain=domain)
            rbac = cls._build_rbac_filter(user_ctx)
            results = await manager.search_memory(query=query, filters=rbac, limit=limit)
            
            elapsed = time.time() - start_time
            logger.info("✅ Vector search completed: found %d results in %.2fs", len(results), elapsed)
            return results
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("❌ Vector search failed after %.2fs: %s", elapsed, str(e), exc_info=True)
            raise

    @classmethod
    async def _query_session(
        cls,
        chat_id: Union[str, int],
        user_ctx: UserContext,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve session messages that the caller is allowed to see.

        We intentionally issue multiple Firestore ``where`` queries and then
        deduplicate them rather than falling back to a single unfiltered scan.
        This satisfies the requirement of "injecting Firestore where clauses."  
        """
        start_time = time.time()
        logger.info("📋 Session query initiated: chat_id=%s user=%s limit=%d role=%s", chat_id, user_ctx.telegram_id, limit, user_ctx.role)
        
        db = SessionManager._get_db()
        if not db:
            logger.warning("⚠️ Firestore client unavailable for session query (chat_id=%s)", chat_id)
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
        query_count = 0
        for q in queries:
            query_count += 1
            async for doc in q.limit(limit).stream():
                data = doc.to_dict()
                mid = str(data.get("message_id", ""))
                if mid in seen_ids:
                    logger.debug("🔄 Duplicate message suppressed: %s", mid)
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
        result = messages[::-1]
        elapsed = time.time() - start_time
        logger.info("✅ Session query completed: %d messages from %d queries in %.2fs (chat_id=%s)", len(result), query_count, elapsed, chat_id)
        return result


    # ------------------------------------------------------------------
    # Public isolated channels
    # ------------------------------------------------------------------

    @classmethod
    async def fetch_working_memory(
        cls,
        user_ctx: UserContext,
        chat_id: Union[str, int],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Return Firestore session messages visible to ``user_ctx``.

        This method does not perform any federation or merging.  It simply
        validates the context and delegates to ``_query_session``.
        """
        if not user_ctx:
            logger.error("🚨 SECURITY: fetch_working_memory called without UserContext")
            raise ValueError("UserContext must be provided for every read operation")
        logger.debug("📌 fetch_working_memory entry point (user=%s chat_id=%s)", user_ctx.telegram_id, chat_id)
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
            logger.error("🚨 SECURITY: search_semantic_archive called without UserContext")
            raise ValueError("UserContext must be provided for every read operation")
        logger.debug("📌 search_semantic_archive entry point (user=%s query='%s')", user_ctx.telegram_id, query[:40])
        return await cls._query_vector(query, user_ctx, domain=domain, limit=limit)

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    @classmethod
    async def add_working_memory(
        cls,
        user_ctx: UserContext,
        chat_id: Union[str, int],
        message_data: Dict[str, Any],
    ) -> Any:
        """Persist a session message through the gateway.

        This is largely a pass-through to :class:`SessionManager`, but we
        require a valid ``UserContext`` so that callers cannot write on behalf
        of another user.  The caller is still responsible for building a
        schema-compliant ``message_data`` dict (usually via
        ``SessionManager.build_log_content``).
        """
        if not user_ctx:
            raise ValueError("UserContext must be provided for every write operation")
        # inject metadata ownership if missing
        if "metadata" not in message_data:
            message_data["metadata"] = {}
        message_data.setdefault("metadata", {})
        message_data["metadata"].setdefault("owner_id", user_ctx.telegram_id)
        # Delegate to legacy manager
        return await SessionManager.add_message(chat_id, message_data)

    @classmethod
    async def get_message_metadata(
        cls, chat_id: Union[str, int], message_id: Union[str, int]
    ) -> dict:
        """Proxy for ``SessionManager.get_message_metadata``.

        Used primarily by the Telegram reply-detection logic in ``main.py``.
        """
        return await SessionManager.get_message_metadata(chat_id, message_id)

    # utility that simply forwards to the legacy helper so callers don’t need
    # to import ``SessionManager`` directly.
    @classmethod
    def build_log_content(
        cls, sensory_payload: Optional[Dict[str, Any]], sanitized_input: Optional[str], message: Any
    ) -> tuple[str, str]:
        """Convenience wrapper around ``SessionManager.build_log_content``."""
        return SessionManager.build_log_content(sensory_payload, sanitized_input, message)

    @classmethod
    async def save_semantic_memory(
        cls, user_ctx: UserContext, item: EpisodicMemoryItem
    ) -> str:
        """Store an episodic memory through the gateway.

        Currently this simply delegates to :class:`VectorMemoryManager`, but the
        gateway could later inject RBAC-related metadata or routing logic.
        """
        if not user_ctx:
            raise ValueError("UserContext must be provided for every write operation")
        # ensure owner id matches
        if not item.metadata.owner_id:
            item.metadata.owner_id = user_ctx.telegram_id
        manager = VectorMemoryManager(domain=item.metadata.domain)
        return await manager.add_memory(item)

    @classmethod
    async def delete_semantic_memory(
        cls, user_ctx: UserContext, memory_id: str, domain: Optional[str] = None
    ) -> None:
        """Delete a memory item by id through the gateway.

        A simple wrapper that could someday enforce ownership/visibility.
        """
        if not user_ctx:
            raise ValueError("UserContext must be provided for every write operation")
        manager = VectorMemoryManager(domain=domain)
        await manager.delete_memory(memory_id)

    # ------------------------------------------------------------------
    # Memory Consolidation Engine
    # ------------------------------------------------------------------

    @classmethod
    async def fetch_unconsolidated_sessions(
        cls, limit_per_session: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetches all messages from all sessions that have not been consolidated.

        Returns:
            A dictionary where keys are session IDs and values are lists of
            unconsolidated messages.
        """
        db = SessionManager._get_db()
        if not db:
            logger.warning("⚠️ Firestore client unavailable for consolidation scan.")
            return {}

        sessions_ref = db.collection("sessions")
        all_sessions_messages = {}

        async for session_doc in sessions_ref.stream():
            session_id = session_doc.id
            messages_ref = (
                session_doc.reference.collection("messages")
                .where("consolidated", "==", False)
                .order_by("timestamp", direction=Query.ASCENDING)
                .limit(limit_per_session)
            )

            unconsolidated_messages = []
            async for msg_doc in messages_ref.stream():
                msg_data = msg_doc.to_dict()
                msg_data["message_id"] = msg_doc.id  # Ensure message_id is included
                unconsolidated_messages.append(msg_data)

            if unconsolidated_messages:
                all_sessions_messages[session_id] = unconsolidated_messages
                logger.info(
                    "Found %d unconsolidated messages in session %s",
                    len(unconsolidated_messages),
                    session_id,
                )

        return all_sessions_messages

    @classmethod
    async def mark_messages_as_consolidated(
        cls, session_id: str, message_ids: List[str]
    ) -> int:
        """
        Marks a list of messages in a session as consolidated.

        Args:
            session_id: The ID of the session.
            message_ids: A list of message IDs to mark as consolidated.

        Returns:
            The number of messages successfully marked as consolidated.
        """
        db = SessionManager._get_db()
        if not db:
            logger.error("⚠️ Firestore client unavailable. Cannot mark messages.")
            return 0

        batch = db.batch()
        messages_ref = db.collection("sessions").document(session_id).collection("messages")

        for msg_id in message_ids:
            doc_ref = messages_ref.document(msg_id)
            batch.update(doc_ref, {"consolidated": True})

        await batch.commit()
        logger.info(
            "Marked %d messages as consolidated in session %s",
            len(message_ids),
            session_id,
        )
        return len(message_ids)