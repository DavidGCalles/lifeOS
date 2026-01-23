import asyncio
from src.schemas.memory import EpisodicMemoryItem, EpisodicMemoryMetadata
from src.memory_manager import VectorMemoryManager

async def run_test():
    print("🧠 Initializing Memory Manager...")
    manager = VectorMemoryManager()
    
    # 1. Crear un recuerdo válido
    print("\n📝 Creating Memory Item...")
    memory = EpisodicMemoryItem(
        content="El usuario prefiere que las reuniones duren máximo 15 minutos.",
        metadata=EpisodicMemoryMetadata(
            domain="professional",
            type="preference",
            source="user_chat"
        )
    )
    
    # 2. Guardar
    print(f"💾 Saving memory ID: {memory.id}")
    await manager.add_memory(memory)
    
    # 3. Buscar (Query Semántica)
    query = "duración reuniones"
    print(f"\n🔍 Searching for: '{query}'")
    results = await manager.search_memory(query=query)
    
    found = False
    for res in results:
        print(f"   > Found: [{res.metadata.type}] {res.content} (Score match implied)")
        if res.id == memory.id:
            found = True
            
    if found:
        print("\n✅ TEST PASSED: Cycle Save -> Recall working.")
    else:
        print("\n❌ TEST FAILED: Memory not found.")

    # 4. Delete
    print(f"\n🗑️ Deleting memory ID: {memory.id}")
    await manager.delete_memory(memory.id)
    print("✅ Memory deleted.")

if __name__ == "__main__":
    asyncio.run(run_test())