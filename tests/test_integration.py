import pytest
import asyncio
from uuid import UUID
from src.models import MemoryNode, MemoryStoreConfig, ZoomLevel
from src.zh_tw.memory_store import MemoryStore
from src.zh_tw.memory_vector import MemoryVectorStore
from src.zh_tw.embedding_provider import OllamaEmbeddingProvider
from src.zh_tw.memory_zoom import MemoryZoom
from src.memory_graph import MemoryGraph, RelationType
import inspect
print(f"MemoryGraph file: {inspect.getfile(MemoryGraph)}")

@pytest.fixture
async def engine_components():
    config = MemoryStoreConfig()
    store = MemoryStore(config)
    await store.connect()
    await store.init_schema()
    
    vector_store = MemoryVectorStore(config)
    vector_store.init_index()
    
    embedding_provider = OllamaEmbeddingProvider()
    zoom_manager = MemoryZoom()
    graph = MemoryGraph()
    
    yield {
        "store": store,
        "vector_store": vector_store,
        "embedding_provider": embedding_provider,
        "zoom_manager": zoom_manager,
        "graph": graph
    }
    
    await store.disconnect()

@pytest.mark.asyncio
async def test_full_memory_lifecycle(engine_components):
    store = engine_components["store"]
    v_store = engine_components["vector_store"]
    provider = engine_components["embedding_provider"]
    zoom = engine_components["zoom_manager"]
    graph = engine_components["graph"]
    
    # 1. 紀錄一段新記憶
    content = "今天我跟王小明討論了關於『阿爾法專案』的預算問題，我們決定增加 20% 的硬體採購費用。"
    embedding = await provider.get_embedding(content)
    
    memory = MemoryNode(
        content=content,
        embedding=embedding,
        importance=0.9
    )
    
    # 2. 存儲到資料庫
    await store.insert(memory)
    
    # 3. 建立索引
    v_store.add_memory(memory)
    
    # 4. 提取實體並加入圖譜
    entities = graph.extract_entities(content)
    graph.add_memory(memory.id, entities=entities)
    
    # 5. 語義檢索測試
    query = "預算增加"
    query_embedding = await provider.get_embedding(query)
    results = v_store.search(query_embedding, k=1)
    
    assert len(results) > 0
    match_id, distance = results[0]
    assert match_id == str(memory.id)
    
    # 6. Zoom 縮放測試
    # 手動模擬摘要 (通常這會由另一層 LLM 完成，這裡測試結構)
    memory.summary_l1 = "討論阿爾法專案預算，決議增加 20% 硬體費用。"
    memory.summary_l0 = "阿爾法專案預算增加。"
    
    zoom_l0 = zoom.zoom(memory, level=ZoomLevel.L0_SUMMARY)
    assert zoom_l0 == memory.summary_l0
    
    # 7. 聯想跳躍 (Jump-Recall) 測試
    # 建立另一個相關記憶
    content2 = "阿爾法專案的硬體採購清單包含伺服器和工作站。"
    memory2 = MemoryNode(
        content=content2,
        embedding=await provider.get_embedding(content2)
    )
    await store.insert(memory2)
    graph.add_memory(memory2.id, entities=graph.extract_entities(content2))
    
    # 建立連接：memory -> memory2 (ELABORATES)
    graph.connect(memory.id, memory2.id, RelationType.ELABORATES)
    
    # 從記憶 1 聯想到記憶 2
    related = graph.jump_recall(memory.id)
    assert len(related) > 0
    assert related[0][0] == memory2.id
    assert related[0][1] == RelationType.ELABORATES
