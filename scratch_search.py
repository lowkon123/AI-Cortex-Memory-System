import asyncio
from src.models import MemoryStoreConfig
from src.zh_tw.memory_store import MemoryStore
from src.zh_tw.memory_vector import MemoryVectorStore
from src.zh_tw.embedding_provider import OllamaEmbeddingProvider
from uuid import UUID

async def test_search():
    config = MemoryStoreConfig()
    store = MemoryStore(config)
    await store.connect()
    v_store = MemoryVectorStore(config)
    v_store.init_index()
    
    # Load
    all_memories = await store.list_all(limit=1000)
    for m in all_memories:
        if m.embedding:
            v_store.add_memory(m)
            
    provider = OllamaEmbeddingProvider(model="bge-m3")
    query = "我叫什麼名字？"
    query_emb = await provider.get_embedding(query)
    
    results = v_store.search(query_emb, k=5)
    print("Search results for:", query)
    for mem_id, dist in results:
        mem = await store.get(UUID(mem_id))
        print(f"Dist: {dist:.3f} | L0: {mem.summary_l0} | Text: {mem.content[:50]}")
    await store.disconnect()

if __name__ == "__main__":
    import asyncio
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(test_search())
