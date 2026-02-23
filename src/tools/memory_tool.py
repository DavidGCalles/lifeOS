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
from src.memory_manager import VectorMemoryManager
from src.identity_manager import UserContext
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
            manager = VectorMemoryManager()
            logger.info("RememberTool invoked by %s. Adding memory (len=%d)...", author_name, len(content))
            
            # Construimos el objeto estricto
            # Nota: Pydantic v2 valida los enums automáticamente
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
            
            mem_id = await manager.add_memory(memory)
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

    async def _run(self, query: str, category: str | None = None) -> str:
        try:
            manager = VectorMemoryManager(domain=MemoryDomainType.EPISODIC)
            logger.debug("RecallTool query=%s category=%s", query, category)
            
            filters = {}
            if category:
                filters["category"] = category

            results = await manager.search_memory(query=query, filters=filters if filters else None)
            
            if not results:
                logger.info("RecallTool: no results for query=%s", query)
                return "No relevant memories found."
            
            # List comprehension moderna y f-strings
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

    async def _run(self, query: str) -> str:
        try:
            manager = VectorMemoryManager(domain=MemoryDomainType.EPISODIC)
            logger.info("ForgetTool invoked. Query=%s", query)
            
            # 1. Primero buscamos qué vamos a borrar (para confirmar)
            # Buscamos el top 1 más similar
            results = await manager.search_memory(query=query, limit=1)
            
            if not results:
                logger.info("ForgetTool: no match for query=%s", query)
                return f"❌ Could not find any memory resembling '{query}' to delete."
            
            target_memory = results[0]
            
            # 2. Borramos usando el ID que hemos recuperado
            # Necesitas añadir este método .delete() al Manager (ver abajo)
            await manager.delete_memory(target_memory.id)
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