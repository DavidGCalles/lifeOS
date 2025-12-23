import os
import chromadb
from chromadb.config import Settings
from src.schemas.memory import EpisodicMemoryItem

class VectorMemoryManager:
    """
    Repository Layer for Episodic Memory.
    Decouples the application logic from the specific database implementation (ChromaDB).
    """
    _client = None
    _collection = None

    def __init__(self, collection_name: str = "episodic_memory_v1"):
        self.collection_name = collection_name
        self._initialize_client()

    def _initialize_client(self):
        """
        Connects to ChromaDB Service.
        Uses Singleton pattern to avoid multiple connections.
        """
        if VectorMemoryManager._client is None:
            host = os.getenv("CHROMA_HOST", "localhost")
            port = os.getenv("CHROMA_PORT", "8000")
            
            print(f"🔌 Connecting to Memory Store at {host}:{port}...")
            
            try:
                VectorMemoryManager._client = chromadb.HttpClient(
                    host=host,
                    port=port,
                    settings=Settings(allow_reset=True, anonymized_telemetry=False)
                )
            except Exception as e:
                raise ConnectionError(f"Failed to connect to ChromaDB: {e}")

        # Get or Create Collection
        if VectorMemoryManager._collection is None:
            VectorMemoryManager._collection = VectorMemoryManager._client.get_or_create_collection(
                name=self.collection_name,
                # metadata={"hnsw:space": "cosine"} # Explicit distance metric if needed
            )

    def add_memory(self, item: EpisodicMemoryItem) -> str:
        """
        Persists a strictly typed memory item into the vector store.
        """
        payload = item.to_chroma_payload()
        
        try:
            VectorMemoryManager._collection.add(
                ids=[payload["id"]],
                documents=[payload["document"]],
                metadatas=[payload["metadata"]]
            )
            return payload["id"]
        except Exception as e:
            # Aquí podrías loguear el error a un fichero
            print(f"❌ Error saving memory: {e}")
            raise e

    def search_memory(
        self, 
        query: str, 
        filters: dict | None = None, 
        limit: int = 5
    ) -> list[EpisodicMemoryItem]:
        """
        Semantic search retrieving structured objects.
        
        Args:
            query: The natural language text to search for.
            filters: Metadata filters (e.g., {"domain": "finance"}).
            limit: Max results.
        """
        try:
            results = VectorMemoryManager._collection.query(
                query_texts=[query],
                n_results=limit,
                where=filters if filters else None
            )
            
            # Chroma returns lists of lists (batch format). We process the first batch.
            # Structure: {'ids': [['id1']], 'documents': [['text1']], 'metadatas': [[{'key': 'val'}]]}
            
            found_items = []
            
            # Check if we have results
            if not results['ids'] or len(results['ids'][0]) == 0:
                return []

            count = len(results['ids'][0])
            
            for i in range(count):
                item = EpisodicMemoryItem.from_chroma_result(
                    id=results['ids'][0][i],
                    document=results['documents'][0][i],
                    metadata=results['metadatas'][0][i]
                )
                found_items.append(item)
                
            return found_items

        except Exception as e:
            print(f"❌ Error searching memory: {e}")
            return []

    def delete_memory(self, memory_id: str):
        """
        Hard delete of a memory item by ID.
        """
        try:
            VectorMemoryManager._collection.delete(ids=[memory_id])
            print(f"🗑️ Memory {memory_id} deleted.")
        except Exception as e:
            print(f"❌ Error deleting memory {memory_id}: {e}")
            raise e
    def get_stats(self):
        """Debug helper"""
        return {
            "count": VectorMemoryManager._collection.count(),
            "name": self.collection_name
        }