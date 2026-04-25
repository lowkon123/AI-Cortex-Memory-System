"""Knowledge Graph Manager (Cortex 2.0).

This module manages relationships between memory nodes and provides 
graph traversal capabilities to expand retrieval scope and discover knowledge links.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from ..models import MemoryRelation, RelationType
from .memory_store import MemoryStore


class KnowledgeGraph:
    """Manages edges and weights in the memory graph."""

    def __init__(self, store: MemoryStore):
        """Initialize KnowledgeGraph with a MemoryStore.

        Args:
            store: The MemoryStore instance to use for persistence.
        """
        self.store = store

    async def link(
        self,
        source_id: UUID,
        target_id: UUID,
        relation_type: RelationType,
        weight: float = 1.0,
    ) -> None:
        """Establish a link between two nodes."""
        await self.store.add_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type.value,
            weight=weight,
        )

    async def unlink(
        self, source_id: UUID, target_id: UUID, relation_type: RelationType
    ) -> bool:
        """Remove a link between two nodes."""
        return await self.store.delete_relation(source_id, target_id, relation_type.value)

    async def get_neighbors(
        self, memory_id: UUID, depth: int = 1, relation_types: Optional[list[RelationType]] = None
    ) -> list[UUID]:
        """Fetch neighbor nodes of a specific memory.
        
        Currently only supports traversal depth of 1.
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
        """Find all nodes that conflict with the specified node."""
        relations = await self.store.get_relations(memory_id)
        conflicts = []
        for rel in relations:
            if rel["relation_type"] == RelationType.CONTRADICTS.value:
                other_id = rel["target_id"] if rel["source_id"] == memory_id else rel["source_id"]
                conflicts.append(other_id)
        return conflicts
