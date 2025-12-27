from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Importamos nuestros Schemas y el Manager
from src.schemas.memory import (
    EpisodicMemoryItem, 
    EpisodicMemoryMetadata, 
    MemoryDomain, 
    MemoryType, 
    MemorySource
)
from src.memory_manager import VectorMemoryManager
from src.identity_manager import UserContext

# --- INPUT SCHEMAS ---

class RememberInput(BaseModel):
    """Input schema for saving a memory."""
    content: str = Field(..., description="The factual content, decision, or insight to remember.")
    domain: MemoryDomain = Field(..., description="The category of the memory (professional, finance, health, etc).")
    type: MemoryType = Field(..., description="The nature of the memory (fact, preference, plan, decision).")
    tags: str | None = Field(None, description="Comma-separated keywords for context.")

class RecallInput(BaseModel):
    """Input schema for searching memories."""
    query: str = Field(..., description="The semantic query to search for relevant memories.")
    domain: MemoryDomain | None = Field(None, description="Optional filter: restrict search to a specific domain.")

class ForgetInput(BaseModel):
    """Input schema for deleting a memory."""
    query: str = Field(..., description="The content of the memory to forget. Be specific to avoid deleting wrong items.")

# --- THE TOOLS ---

class RememberTool(BaseTool):
    name: str = "save_memory"
    description: str = (
        "Use this tool to PERMANENTLY save important information, decisions, "
        "preferences, or plans. Do not use for trivial chat history. "
        "Requires categorizing the memory by domain and type."
    )
    args_schema: type[BaseModel] = RememberInput
    # Estado interno para guardar quién está llamando a la tool
    _current_user: UserContext | None = None

    def set_context(self, user: UserContext):
        """Inyecta el usuario actual antes de ejecutar la tool."""
        self._current_user = user

    def _run(self, content: str, domain: str, type: str, tags: str | None = None) -> str:
        # Determinamos el autor
        author_name = self._current_user.name if self._current_user else "unknown_system"
        try:
            manager = VectorMemoryManager()
            
            # Construimos el objeto estricto
            # Nota: Pydantic v2 valida los enums automáticamente
            memory = EpisodicMemoryItem(
                content=content,
                metadata=EpisodicMemoryMetadata(
                    domain=domain, # type: ignore (Pydantic valida el string contra el Enum)
                    type=type,     # type: ignore
                    source=MemorySource.AGENT_REFLECTION, 
                    context_tags=tags
                ),
                created_by=author_name 
            )
            
            mem_id = manager.add_memory(memory)
            return f"✅ Memory saved successfully with ID: {mem_id}"
            
        except Exception as e:
            return f"❌ Error saving memory: {str(e)}"

class RecallTool(BaseTool):
    name: str = "search_memory"
    description: str = (
        "Use this tool to retrieve past context, decisions, or facts about the user "
        "or projects. Useful when you need to answer 'What did we say about X?'."
    )
    args_schema: type[BaseModel] = RecallInput

    def _run(self, query: str, domain: str | None = None) -> str:
        try:
            manager = VectorMemoryManager()
            
            filters = {}
            if domain:
                filters["domain"] = domain

            results = manager.search_memory(query=query, filters=filters if filters else None)
            
            if not results:
                return "No relevant memories found."
            
            # List comprehension moderna y f-strings
            formatted_output = "Found relevant memories:\n" + "\n".join(
                [f"- [{item.created_at}] ({item.metadata.type}): {item.content}" for item in results]
            )
            
            return formatted_output

        except Exception as e:
            return f"❌ Error retrieving memories: {str(e)}"
        
class ForgetTool(BaseTool):
    name: str = "forget_memory"
    description: str = (
        "Use this tool to DELETE obsolete, incorrect, or deprecated information "
        "from the memory. Use cautiously. It searches for the most similar memory "
        "and deletes it."
    )
    args_schema: type[BaseModel] = ForgetInput

    def _run(self, query: str) -> str:
        try:
            manager = VectorMemoryManager()
            
            # 1. Primero buscamos qué vamos a borrar (para confirmar)
            # Buscamos el top 1 más similar
            results = manager.search_memory(query=query, limit=1)
            
            if not results:
                return f"❌ Could not find any memory resembling '{query}' to delete."
            
            target_memory = results[0]
            
            # 2. Borramos usando el ID que hemos recuperado
            # Necesitas añadir este método .delete() al Manager (ver abajo)
            manager.delete_memory(target_memory.id)
            
            return (
                f"🗑️ DELETED Memory ID {target_memory.id}\n"
                f"Content: '{target_memory.content}'\n"
                f"Metadata: {target_memory.metadata}"
            )

        except Exception as e:
            return f"❌ Error deleting memory: {str(e)}"