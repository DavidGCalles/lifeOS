import os
import requests
import logging
from qdrant_client import QdrantClient, models
from src.schemas.memory import EpisodicMemoryItem, EpisodicMemoryMetadata

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VectorMemoryManager:
    """
    Repository Layer for Episodic Memory.
    Decouples the application logic from the specific database implementation (Qdrant).
    """
    _client: QdrantClient = None
    _collection_name: str = "episodic_memory_v1"

    def __init__(self, collection_name: str = "episodic_memory_v1"):
        self._collection_name = collection_name
        self._initialize_client()
        self._ensure_collection()

    def _initialize_client(self):
        """
        Connects to Qdrant Service using a smart connection pattern.
        - If QDRANT_API_KEY is present, it assumes Cloud/HTTPS connection.
        - Otherwise, it falls back to local Docker/HTTP connection.
        Uses Singleton pattern to avoid multiple connections.
        """
        if VectorMemoryManager._client is None:
            host = os.getenv("QDRANT_HOST", "qdrant")
            port = int(os.getenv("QDRANT_PORT", 6333))
            api_key = os.getenv("QDRANT_API_KEY")

            logger.info("🔌 Connecting to Memory Store...")

            try:
                if api_key:
                    # Cloud Mode (assumes HTTPS)
                    logger.info(f"   -> Mode: Cloud, URL: {host}")
                    VectorMemoryManager._client = QdrantClient(url=host, api_key=api_key)
                else:
                    # Docker Mode (Plain HTTP)
                    logger.info(f"   -> Mode: Docker, Host: {host}, Port: {port}")
                    VectorMemoryManager._client = QdrantClient(host=host, port=port)
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}", exc_info=True)
                raise ConnectionError(f"Failed to connect to Qdrant: {e}")

    def _ensure_collection(self):
        """
        Checks if the collection exists and creates it if it doesn't.
        This operation is idempotent.
        """
        try:
            self._client.get_collection(collection_name=self._collection_name)
        except Exception:
            logger.info(f"Collection '{self._collection_name}' not found. Creating a new one...")
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=768, 
                    distance=models.Distance.COSINE
                ),
            )
            logger.info(f"✅ Collection '{self._collection_name}' created successfully.")


    def _get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding for the given text using the LiteLLM proxy.
        """
        litellm_url = os.getenv("LITELLM_URL", "http://localhost:4000")
        if not litellm_url.startswith("http"):
            litellm_url = f"http://{litellm_url}"
        
        embedding_url = f"{litellm_url.rstrip('/')}/v1/embeddings"
        
        headers = {"Content-Type": "application/json"}
        data = {
            "model": "text-embedding-004",
            "input": [text]
        }
        
        try:
            response = requests.post(embedding_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            embedding_data = response.json().get("data")
            if embedding_data and len(embedding_data) > 0:
                return embedding_data[0].get("embedding")
            raise ValueError("Invalid embedding response format from LiteLLM")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting embedding from LiteLLM proxy at {embedding_url}: {e}", exc_info=True)
            raise

    def add_memory(self, item: EpisodicMemoryItem) -> str:
        """
        Persists a strictly typed memory item into the vector store.
        """
        vector = self._get_embedding(item.content)
        
        try:
            self._client.upsert(
                collection_name=self._collection_name,
                points=[
                    models.PointStruct(
                        id=item.id,
                        vector=vector,
                        payload={
                            **item.metadata.model_dump(),
                            "content": item.content,
                            "created_at": item.created_at
                        }
                    )
                ],
                wait=True
            )
            logger.info(f"Successfully added memory {item.id}")
            return item.id
        except Exception as e:
            logger.error(f"Error saving memory {item.id}: {e}", exc_info=True)
            raise e

    def search_memory(
        self, 
        query: str, 
        filters: dict | None = None, 
        limit: int = 5
    ) -> list[EpisodicMemoryItem]:
        """
        Semantic search retrieving structured objects.
        """
        query_vector = self._get_embedding(query)
        
        filter_conditions = []
        if filters:
            for key, value in filters.items():
                filter_conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                )
        
        qdrant_filter = models.Filter(must=filter_conditions) if filter_conditions else None

        try:
            result_obj = self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,         # <-- CAMBIO 1: 'query_vector' ahora es 'query'
                query_filter=qdrant_filter, # <-- Se mantiene 'query_filter'
                limit=limit
            )
            
            # FIX ADR-007: Ahora devuelve un objeto wrapper, extraemos la lista de puntos
            results = result_obj.points
            
            found_items = []
            for point in results:
                metadata_payload = {k: v for k, v in point.payload.items() if k not in ["content", "created_at"]}
                metadata = EpisodicMemoryMetadata(**metadata_payload)
                
                item = EpisodicMemoryItem(
                    id=point.id,
                    content=point.payload["content"],
                    created_at=point.payload["created_at"],
                    metadata=metadata
                )
                found_items.append(item)
            
            logger.info(f"Found {len(found_items)} memories for query: '{query}'")
            return found_items

        except Exception as e:
            logger.error(f"Error searching memory for query '{query}': {e}", exc_info=True)
            return []

    def delete_memory(self, memory_id: str):
        """
        Hard delete of a memory item by ID.
        """
        try:
            self._client.delete(
                collection_name=self._collection_name,
                points_selector=models.PointIdsList(points=[memory_id]),
            )
            logger.info(f"🗑️ Memory {memory_id} deleted.")
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}", exc_info=True)
            raise e