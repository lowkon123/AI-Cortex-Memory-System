import asyncio
from uuid import uuid4
from src.models import MemoryNode, MemoryStoreConfig, ZoomLevel, MemoryStatus
from src.zh_tw.memory_store import MemoryStore
from src.zh_tw.memory_vector import MemoryVectorStore
from src.zh_tw.embedding_provider import OllamaEmbeddingProvider
from src.zh_tw.memory_zoom import MemoryZoom
from src.memory_graph import MemoryGraph, RelationType
from src.memory_feedback import MemoryFeedback

async def main():
    print("--- 啟動 Cortex Memory Engine 演示 (繁體中文) ---")
    
    # 1. 初始化組件
    config = MemoryStoreConfig()
    store = MemoryStore(config)
    await store.connect()
    await store.init_schema()
    
    v_store = MemoryVectorStore(config)
    v_store.init_index()
    
    provider = OllamaEmbeddingProvider()
    zoom = MemoryZoom()
    graph = MemoryGraph()
    feedback = MemoryFeedback()
    
    print("正在清空舊數據以進行乾淨演示...")
    import asyncpg
    conn = await asyncpg.connect(host=config.host, user=config.user, password=config.password, database=config.database)
    await conn.execute("TRUNCATE memories CASCADE;")
    await conn.close()
    
    # 2. 存入一系列相關記憶
    memories_data = [
        {
            "content": "阿爾法專案（Project Alpha）是我們下半年的核心開發計畫，主要目標是提升 AI 的推理速度。",
            "importance": 0.9,
            "entities": ["阿爾法專案", "AI", "推理速度"]
        },
        {
            "content": "王小明是阿爾法專案的首席架構師，他非常擅長優化向量資料庫。",
            "importance": 0.8,
            "entities": ["王小明", "阿爾法專案", "向量資料庫"]
        },
        {
            "content": "在昨天的會議中，王小明提到硬體成本超支了 15%，我們需要調整採購清單。",
            "importance": 0.7,
            "entities": ["王小明", "會議", "硬體成本"]
        }
    ]
    
    nodes = []
    for data in memories_data:
        print(f"存入記憶: {data['content'][:30]}...")
        # 生成向量
        emb = await provider.get_embedding(data["content"])
        
        node = MemoryNode(
            content=data["content"],
            embedding=emb,
            importance=data["importance"],
            summary_l1=f"關於『{data['entities'][0]}』的關鍵資訊。",
            summary_l0=data["entities"][0]
        )
        
        await store.insert(node)
        v_store.add_memory(node)
        graph.add_memory(node.id, entities=data["entities"])
        nodes.append(node)
    
    # 手動建立圖譜連接: 記憶 0 (專案) <-> 記憶 1 (架構師)
    graph.connect(nodes[0].id, nodes[1].id, RelationType.REMINDS)
    # 記憶 1 (架構師) <-> 記憶 2 (會議)
    graph.connect(nodes[1].id, nodes[2].id, RelationType.ELABORATES)
    
    print("\n--- 演示 1: 語義檢索 (Semantic Search) ---")
    query = "誰負責優化資料庫？"
    q_emb = await provider.get_embedding(query)
    results = v_store.search(q_emb, k=1)
    if results:
        match = await store.get(results[0][0])
        print(f"問：{query}")
        print(f"答：{match.content}")

    print("\n--- 演示 2: 關聯性跳躍 (Jump-Recall) ---")
    print(f"從『阿爾法專案』出發，自動聯想相關資訊...")
    jumps = graph.jump_recall(nodes[0].id, max_hops=2)
    for target_id, rel, depth in jumps:
        target = await store.get(target_id)
        print(f"  [跳躍 {depth} 步] ({rel.value}) -> {target.content[:40]}...")

    print("\n--- 演示 3: 記憶縮放 (Memory Zoom) ---")
    print(f"原始內容 (L2): {nodes[0].content}")
    zoom.set_level(ZoomLevel.L1_ABSTRACT)
    print(f"摘要內容 (L1): {zoom.get_content(nodes[0])}")
    zoom.set_level(ZoomLevel.L0_SUMMARY)
    print(f"極簡內容 (L0): {zoom.get_content(nodes[0])}")

    print("\n--- 演示 4: 強化反饋 (Reinforcement Feedback) ---")
    print(f"原始重要性: {nodes[0].importance}")
    feedback.apply_boost(nodes[0], 0.95)
    print(f"強化後重要性: {nodes[0].importance}")

    await store.disconnect()
    print("\n--- 演示結束 ---")

if __name__ == "__main__":
    asyncio.run(main())
