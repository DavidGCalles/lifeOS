import os
import chromadb
from chromadb.config import Settings
import sys

def test_chroma_connection():
    print("Testing ChromaDB Connection...")
    
    # Configuración para conectar al servicio Dockerizado
    chroma_host = os.getenv("CHROMA_HOST", "localhost") # localhost si corres el test desde fuera de docker
    chroma_port = os.getenv("CHROMA_PORT", "8000")
    
    try:
        client = chromadb.HttpClient(
            host=chroma_host, 
            port=chroma_port,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        print(f"✅ Connected to Chroma at {chroma_host}:{chroma_port}")
        
        # Test básico de Heartbeat
        print(f"💓 Heartbeat: {client.heartbeat()}")
        
        # Crear colección de prueba
        collection_name = "test_verification_collection"
        
        # Limpieza previa por si acaso
        try:
            client.delete_collection(collection_name)
        except:
            pass

        collection = client.create_collection(name=collection_name)
        print(f"✅ Collection '{collection_name}' created.")

        # Insertar datos dummy (Chroma usará su embedding por defecto si no especificamos, 
        # para este test de conectividad es suficiente. 
        # Si quieres probar el embedding de Google, necesitamos instanciar la embedding function).
        
        collection.add(
            documents=["This is a test document about axolotls", "This is a test about banking software"],
            metadatas=[{"source": "test"}, {"source": "test"}],
            ids=["id1", "id2"]
        )
        print("✅ Documents inserted.")

        # Query
        results = collection.query(
            query_texts=["axolotls"],
            n_results=1
        )
        
        print(f"🔍 Query Result: {results['documents'][0]}")
        
        if "axolotls" in results['documents'][0][0]:
            print("🎉 SUCCESS: Vector retrieval works.")
        else:
            print("⚠️ WARNING: Retrieval content mismatch (check embedding logic).")
            
        # Cleanup
        client.delete_collection(collection_name)
        print("🧹 Cleanup done.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_chroma_connection()