"""知識圖譜管理器 (Cortex 2.0)。

此模組負責管理記憶節點之間的關係，並提供圖譜遍歷功能，
用於擴展檢索範圍和發現知識關聯。
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from ..models import MemoryRelation, RelationType
from .memory_store import MemoryStore


class KnowledgeGraph:
    """管理記憶圖譜中的邊與權重。"""

    def __init__(self, store: MemoryStore):
        self.store = store

    async def link(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: RelationType,
        weight: float = 1.0,
    ) -> None:
        """在兩個節點之間建立連結。"""
        await self.store.add_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type.value,
            weight=weight,
        )

    async def unlink(
        self, source_id: UUID, target_id: UUID, relation_type: RelationType
    ) -> bool:
        """移除兩個節點之間的連結。"""
        return await self.store.delete_relation(source_id, target_id, relation_type.value)

    async def get_neighbors(
        self, memory_id: UUID, depth: int = 1, relation_types: Optional[list[RelationType]] = None
    ) -> list[UUID]:
        """獲取指定節點的鄰居節點。
        
        目前僅支持深度為 1 的遍歷。
        """
        relations = await self.store.get_relations(memory_id)
        neighbors = set()
        
        type_values = [rt.value for rt in relation_types] if relation_types else None
        
        for rel in relations:
            if type_values and rel["relation_type"] not in type_values:
                continue
                
            if rel["source_id"] == memory_id:
                neighbors.add(rel["target_id"])
            else:
                neighbors.add(rel["source_id"])
                
        return list(neighbors)

    async def check_conflict(self, memory_id: UUID) -> list[UUID]:
        """尋找與指定節點衝突的所有節點。"""
        relations = await self.store.get_relations(memory_id)
        conflicts = []
        for rel in relations:
            if rel["relation_type"] == RelationType.CONTRADICTS.value:
                other_id = rel["target_id"] if rel["source_id"] == memory_id else rel["source_id"]
                conflicts.append(other_id)
        return conflicts
