import asyncio

import dashboard
from src.models import MemoryStoreConfig
from src.zh_tw.embedding_provider import OllamaEmbeddingProvider
from src.zh_tw.memory_store import MemoryStore


async def main():
    dashboard.store = MemoryStore(MemoryStoreConfig())
    await dashboard.store.connect()
    await dashboard.store.init_schema()
    dashboard.provider = OllamaEmbeddingProvider(model="bge-m3")
    try:
        resp = await dashboard.graph_data()
        print(type(resp))
        print(resp.body.decode("utf-8")[:4000])
    finally:
        await dashboard.store.disconnect()


asyncio.run(main())
