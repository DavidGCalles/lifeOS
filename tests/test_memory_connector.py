import os
import sys
import logging
from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

def test_qdrant_connection():
    """
    Tests the low-level connection to the Qdrant vector database.
    It verifies that the service is online and that we have write permissions.
    """
    logger.info("🚀 Testing Qdrant Connection...")

    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", None)

    try:
        # Initialize Qdrant client
        client = QdrantClient(
            host=qdrant_host, 
            port=6333,
            api_key=qdrant_api_key,
        )
        logger.info(f"✅ Qdrant client initialized for host: {qdrant_host}")

        # 1. Verify Heartbeat with a simple request
        collections_response = client.get_collections()
        logger.info(f"✅ Heartbeat successful. Found {len(collections_response.collections)} collections.")

        # 2. Verify Write Permissions by creating and deleting a dummy collection
        collection_name = "test_connectivity"
        
        # Cleanup if a previous test failed
        try:
            client.delete_collection(collection_name=collection_name)
            logger.info(f"🧹 Cleaned up pre-existing dummy collection '{collection_name}'.")
        except Exception:
            pass # It's ok if it doesn't exist

        # Create collection
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
        logger.info(f"✅ Dummy collection '{collection_name}' created.")

        # Delete collection
        client.delete_collection(collection_name=collection_name)
        logger.info(f"✅ Dummy collection '{collection_name}' deleted.")

        logger.info("\n🎉 SUCCESS: Qdrant Online / Connection Successful")

    except Exception as e:
        logger.error(f"❌ ERROR: Could not connect to Qdrant or perform operations. Details: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_qdrant_connection()