import pytest
import asyncio
from uuid import uuid4
from datetime import datetime
from src.models import MemoryNode, MemoryStoreConfig, MemoryStatus, ZoomLevel
from src.zh_tw.memory_store import MemoryStore

@pytest.fixture
async def store():
    config = MemoryStoreConfig()
    store = MemoryStore(config)
    await store.connect()
    await store.init_schema()
    yield store
    # Cleanup: delete test memories or drop table
    # For now we'll just disconnect
    await store.disconnect()

@pytest.mark.asyncio
async def test_insert_and_get(store):
    node = MemoryNode(
        content="這是一段測試記憶",
        importance=0.8,
        embedding=[0.1] * 1024
    )
    
    # Test Insert
    inserted = await store.insert(node)
    assert inserted.id == node.id
    
    # Test Get
    retrieved = await store.get(node.id)
    assert retrieved is not None
    assert retrieved.content == "這是一段測試記憶"
    assert retrieved.importance == 0.8
    assert retrieved.zoom_level == ZoomLevel.L2_FULL

@pytest.mark.asyncio
async def test_update(store):
    node = MemoryNode(
        content="原始內容",
        importance=0.5,
        embedding=[0.1] * 1024
    )
    await store.insert(node)
    
    node.content = "更新後的內容"
    node.status = MemoryStatus.ARCHIVED
    await store.update(node)
    
    retrieved = await store.get(node.id)
    assert retrieved.content == "更新後的內容"
    assert retrieved.status == MemoryStatus.ARCHIVED

@pytest.mark.asyncio
async def test_delete(store):
    node = MemoryNode(
        content="待刪除記憶",
        embedding=[0.1] * 1024
    )
    await store.insert(node)
    
    deleted = await store.delete(node.id)
    assert deleted is True
    
    retrieved = await store.get(node.id)
    assert retrieved is None

@pytest.mark.asyncio
async def test_list_all(store):
    # Clear existing if needed, but here we just check if we can list
    node1 = MemoryNode(content="記憶1", embedding=[0.1] * 1024)
    node2 = MemoryNode(content="記憶2", embedding=[0.1] * 1024)
    await store.insert(node1)
    await store.insert(node2)
    
    memories = await store.list_all(limit=10)
    assert len(memories) >= 2
    contents = [m.content for m in memories]
    assert "記憶1" in contents
    assert "記憶2" in contents
