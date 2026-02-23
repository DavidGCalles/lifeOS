from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Importamos nuestros Schemas y el Manager
from src.schemas.memory import (
    EpisodicMemoryItem,
    EpisodicMemoryMetadata,
    MemoryCategory,
    MemoryType,
    MemorySource,
    MemoryDomainType,
)
from src.identity_manager import UserContext
from src.memory_gateway import MemoryGateway
from src.logging_config import get_logger
logger = get_logger(__name__) 

# --- INPUT SCHEMAS ---

class RememberInput(BaseModel):
    """Input schema for saving a memory."""
    content: str = Field(..., description="The factual content, decision, or insight to remember.")
    category: MemoryCategory = Field(..., description="The category of the memory (professional, finance, health, etc).")
    type: MemoryType = Field(..., description="The nature of the memory (fact, preference, plan, decision).")
    tags: str | None = Field(None, description="Comma-separated keywords for context.")

class RecallInput(BaseModel):
    """Input schema for searching memories."""
    query: str = Field(..., description="The semantic query to search for relevant memories.")
    category: MemoryCategory | None = Field(None, description="Optional filter: restrict search to a specific category.")

class ForgetInput(BaseModel):
    """Input schema for deleting a memory."""
    query: str = Field(..., description="The content of the memory to forget. Be specific to avoid deleting wrong items.")

# --- THE TOOLS ---

class RememberTool(BaseTool):
    name: str = "save_memory"
    description: str = (
        "Use this tool to PERMANENTLY save important information, decisions, "
        "preferences, or plans. Do not use for trivial chat history. "
        "Requires categorizing the memory by category and type."
    )
    args_schema: type[BaseModel] = RememberInput
    # Estado interno para guardar quién está llamando a la tool
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        """Inyecta el usuario actual antes de ejecutar la tool."""
        self._current_user = user

    async def _run(self, content: str, category: str, type: str, tags: str | None = None) -> str:
        # Determinamos el autor
        author_name = self._current_user.name if self._current_user else "unknown_system"
        owner_id = self._current_user.telegram_id if self._current_user else "unknown"
        try:
            logger.info("RememberTool invoked by %s. Adding memory (len=%d)...", author_name, len(content))

            memory = EpisodicMemoryItem(
                content=content,
                metadata=EpisodicMemoryMetadata(
                    owner_id=owner_id,
                    # domain is fixed by the subclass to EPISODIC, so the caller
                    # only needs to provide the original "category" semantic.
                    category=category,
                    type=type,     # type: ignore
                    source=MemorySource.AGENT_REFLECTION, 
                    context_tags=tags
                ),
                created_by=author_name 
            )

            # delegate through gateway so RBAC metadata and context propagation
            mem_id = await MemoryGateway.save_semantic_memory(self._current_user, memory)
            logger.info("Memory saved: id=%s by=%s", mem_id, author_name)
            return f"✅ Memory saved successfully with ID: {mem_id}"
            
        except Exception as e:
            logger.exception("Error saving memory")
            return f"❌ Error saving memory: {str(e)}"

    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)

class RecallTool(BaseTool):
    name: str = "search_memory"
    description: str = (
        "Use this tool to retrieve past context, decisions, or facts about the user "
        "or projects. Useful when you need to answer 'What did we say about X?'."
    )
    args_schema: type[BaseModel] = RecallInput
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        self._current_user = user
    async def _run(self, query: str, category: str | None = None) -> str:
        try:
            logger.debug("RecallTool query=%s category=%s", query, category)
            # call gateway instead of manager; include user context for RBAC
            results = await MemoryGateway.search_semantic_archive(
                user_ctx=self._current_user,
                query=query,
                limit=5,
                domain=MemoryDomainType.EPISODIC,
            )

            # apply category filtering locally if requested
            if category:
                results = [r for r in results if r.metadata.category.value == category]

            if not results:
                logger.info("RecallTool: no results for query=%s", query)
                return "No relevant memories found."

            formatted_output = "Found relevant memories:\n" + "\n".join(
                [f"- [{item.created_at}] ({item.metadata.type}): {item.content}" for item in results]
            )

            logger.info("RecallTool: found %d results for query=%s", len(results), query)
            return formatted_output

        except Exception as e:
            logger.exception("Error retrieving memories for query=%s", query)
            return f"❌ Error retrieving memories: {str(e)}"

    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)
        
class ForgetTool(BaseTool):
    name: str = "forget_memory"
    description: str = (
        "Use this tool to DELETE obsolete, incorrect, or deprecated information "
        "from the memory. Use cautiously. It searches for the most similar memory "
        "and deletes it."
    )
    args_schema: type[BaseModel] = ForgetInput
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        self._current_user = user

    async def _run(self, query: str) -> str:
        try:
            logger.info("ForgetTool invoked. Query=%s", query)

            # use gateway to search and delete
            results = await MemoryGateway.search_semantic_archive(
                user_ctx=self._current_user,
                query=query,
                limit=1,
                domain=MemoryDomainType.EPISODIC,
            )

            if not results:
                logger.info("ForgetTool: no match for query=%s", query)
                return f"❌ Could not find any memory resembling '{query}' to delete."

            target_memory = results[0]
            await MemoryGateway.delete_semantic_memory(self._current_user, target_memory.id)
            logger.info("ForgetTool: deleted memory id=%s", target_memory.id)

            return (
                f"🗑️ DELETED Memory ID {target_memory.id}\n"
                f"Content: '{target_memory.content}'\n"
                f"Metadata: {target_memory.metadata}"
            )

        except Exception as e:
            logger.exception("Error deleting memory for query=%s", query)
            return f"❌ Error deleting memory: {str(e)}"

    async def run(self, *args, **kwargs):
        return await self._run(*args, **kwargs)