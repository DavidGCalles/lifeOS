import os
import logging
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient, models
from src.schemas.memory import EpisodicMemoryItem, EpisodicMemoryMetadata

from src.logging_config import configure_logging
configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
# 384 for intfloat/multilingual-e5-small (local)
# 768 for text-embedding-004 (Gemini)
EMBEDDING_DIMENSION = 384

class VectorMemoryManager:
    """
    Repository Layer for Episodic Memory.
    Decouples the application logic from the specific database implementation (Qdrant).
    """
    def __init__(self, collection_name: str = "episodic_memory_v1"):
        self._collection_name = collection_name
        self._client = None

    async def _initialize_client(self):
        """
        Connects to Qdrant Service using a smart connection pattern.
        - If QDRANT_API_KEY is present, it assumes Cloud/HTTPS connection.
        - Otherwise, it falls back to local Docker/HTTP connection.
        """
        if self._client is None:
            host = os.getenv("QDRANT_HOST", "qdrant")
            port = int(os.getenv("QDRANT_PORT", 6333))
            api_key = os.getenv("QDRANT_API_KEY")

            logger.info("🔌 Connecting to Memory Store...")

            try:
                if api_key:
                    # Cloud Mode (assumes HTTPS)
                    logger.info(f"   -> Mode: Cloud, URL: {host}")
                    self._client = AsyncQdrantClient(url=host, api_key=api_key)
                else:
                    # Docker Mode (Plain HTTP)
                    logger.info(f"   -> Mode: Docker, Host: {host}, Port: {port}")
                    self._client = AsyncQdrantClient(host=host, port=port)
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}", exc_info=True)
                raise ConnectionError(f"Failed to connect to Qdrant: {e}")

    async def _ensure_collection(self):
        """
        Checks if the collection exists and creates it if it doesn't.
        Also ensures that the necessary payload indexes exist for filtering.
        """
        try:
            await self._client.get_collection(collection_name=self._collection_name)
        except Exception:
            logger.info(f"Collection '{self._collection_name}' not found. Creating a new one...")
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=EMBEDDING_DIMENSION, 
                    distance=models.Distance.COSINE
                ),
            )
            logger.info(f"✅ Collection '{self._collection_name}' created successfully.")

        # --- FIX: Create Payload Indexes for Filtering ---
        # Qdrant operations are idempotent, so we can run this safely on every startup.
        # We index 'domain', 'type', and 'source' to allow fast filtering.
        payload_indexes = ["domain", "type", "source"]
        
        for field in payload_indexes:
            try:
                await self._client.create_payload_index(
                    collection_name=self._collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=False
                )
            except Exception as e:
                # If index already exists or another minor error, we just log it
                logger.debug(f"Index check for '{field}': {e}")


    async def _get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding for the given text using the LiteLLM proxy.
        Uses the 'text-embedding' model configured in LiteLLM which routes to the proper provider.
        """
        litellm_url = os.getenv("LITELLM_URL", "http://localhost:4000")
        if not litellm_url.startswith("http"):
            litellm_url = f"http://{litellm_url}"
            
        client = AsyncOpenAI(
            base_url=f"{litellm_url.rstrip('/')}/v1",
            api_key="sk-fake-key"
        )
        
        try:
            response = await client.embeddings.create(
                model="text-embedding",
                input=[text]
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embedding from LiteLLM proxy: {e}", exc_info=True)
            raise

    async def add_memory(self, item: EpisodicMemoryItem) -> str:
        """
        Persists a strictly typed memory item into the vector store.
        """
        if self._client is None:
            await self._initialize_client()
        await self._ensure_collection()
        vector = await self._get_embedding(item.content)
        
        try:
            await self._client.upsert(
                collection_name=self._collection_name,
                points=[
                    models.PointStruct(
                        id=item.id,
                        vector=vector,
                        payload={
                            **item.metadata.model_dump(),
                            "content": item.content,
                            "created_at": item.created_at,
                            "created_by": item.created_by
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

    async def search_memory(
        self, 
        query: str, 
        filters: dict | None = None, 
        limit: int = 5
    ) -> list[EpisodicMemoryItem]:
        """
        Semantic search retrieving structured objects.
        """
        if self._client is None:
            await self._initialize_client()
        await self._ensure_collection()
        query_vector = await self._get_embedding(query)
        
        filter_conditions = []
        if filters:
            for key, value in filters.items():
                filter_conditions.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                )
        
        qdrant_filter = models.Filter(must=filter_conditions) if filter_conditions else None

        try:
            result_obj = await self._client.query_points(
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
                    metadata=metadata,
                    created_by=point.payload.get("created_by")
                )
                found_items.append(item)
            
            logger.info(f"Found {len(found_items)} memories for query: '{query}'")
            return found_items

        except Exception as e:
            logger.error(f"Error searching memory for query '{query}': {e}", exc_info=True)
            return []

    async def delete_memory(self, memory_id: str):
        """
        Hard delete of a memory item by ID.
        """
        if self._client is None:
            await self._initialize_client()
        try:
            await self._client.delete(
                collection_name=self._collection_name,
                points_selector=models.PointIdsList(points=[memory_id]),
            )
            logger.info(f"🗑️ Memory {memory_id} deleted.")
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}", exc_info=True)
            raise e