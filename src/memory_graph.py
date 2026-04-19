"""Entity-relation graph for associative jump-recall between memories.

This module implements graph-based memory retrieval, allowing
"jump-recall" between related nodes beyond simple similarity search.
"""

from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class RelationType(str, Enum):
    """Types of relations between memory nodes."""

    CAUSAL = "causal"  # A causes B
    CONTRADICTS = "contradicts"  # A contradicts B
    SUPPORTS = "supports"  # A supports B
    ELABORATES = "elaborates"  # A elaborates on B
    REMINDS = "reminds"  # A reminds of B
    UPDATES = "updates"  # A updates B


class MemoryGraph:
    """Entity-relation graph for associative memory retrieval.

    Maintains a graph of memory nodes connected by typed relations,
    enabling traversal-based recall (jump-recall).
    """

    def __init__(self):
        """Initialize the memory graph."""
        self._nodes: dict[UUID, set[UUID]] = {}
        self._relations: dict[tuple[UUID, UUID], RelationType] = {}
        self._entities: dict[str, set[UUID]] = {}

    def add_memory(
        self,
        memory_id: UUID,
        entities: Optional[list[str]] = None,
    ) -> None:
        """Add a memory node to the graph.

        Args:
            memory_id: The ID of the memory node.
            entities: Optional list of entity strings extracted from content.
        """
        if memory_id not in self._nodes:
            self._nodes[memory_id] = set()

        if entities:
            for entity in entities:
                if entity not in self._entities:
                    self._entities[entity] = set()
                self._entities[entity].add(memory_id)

    def connect(
        self,
        from_id: UUID,
        to_id: UUID,
        relation: RelationType,
    ) -> None:
        """Create a directed relation between two memory nodes.

        Args:
            from_id: Source memory ID.
            to_id: Target memory ID.
            relation: Type of relation.
        """
        if from_id not in self._nodes:
            self._nodes[from_id] = set()
        if to_id not in self._nodes:
            self._nodes[to_id] = set()

        self._nodes[from_id].add(to_id)
        self._relations[(from_id, to_id)] = relation

    def jump_recall(
        self,
        memory_id: UUID,
        max_hops: int = 3,
        relation_filter: Optional[list[RelationType]] = None,
    ) -> list[tuple[UUID, RelationType, int]]:
        """Perform jump-recall from a memory through the graph.

        Args:
            memory_id: Starting memory ID.
            max_hops: Maximum traversal depth.
            relation_filter: Optional list of relation types to follow.

        Returns:
            List of (memory_id, relation_type, hop_depth) tuples.
        """
        visited: dict[UUID, int] = {memory_id: 0}
        queue: list[tuple[UUID, int]] = [(memory_id, 0)]
        results: list[tuple[UUID, RelationType, int]] = []

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_hops:
                continue

            if current not in self._nodes:
                continue

            for neighbor in self._nodes[current]:
                if neighbor in visited:
                    continue

                relation = self._relations.get((current, neighbor))
                if relation_filter and relation and relation not in relation_filter:
                    continue

                visited[neighbor] = depth + 1
                results.append((neighbor, relation, depth + 1))
                queue.append((neighbor, depth + 1))

        return results

    def find_related(
        self,
        entity: str,
        relation_filter: Optional[list[RelationType]] = None,
    ) -> list[UUID]:
        """Find memories linked to a specific entity.

        Args:
            entity: The entity string to search for.
            relation_filter: Optional filter by relation types.

        Returns:
            List of related memory IDs.
        """
        if entity not in self._entities:
            return []

        results = []
        for memory_id in self._entities[entity]:
            results.append(memory_id)

        return results

    def get_neighbors(
        self,
        memory_id: UUID,
        relation_filter: Optional[list[RelationType]] = None,
    ) -> list[tuple[UUID, RelationType]]:
        """Get directly connected neighbors of a memory.

        Args:
            memory_id: The memory ID.
            relation_filter: Optional filter by relation types.

        Returns:
            List of (neighbor_id, relation_type) tuples.
        """
        if memory_id not in self._nodes:
            return []

        results = []
        for neighbor in self._nodes[memory_id]:
            relation = self._relations.get((memory_id, neighbor))
            if relation_filter and relation and relation not in relation_filter:
                continue
            results.append((neighbor, relation))

        return results

    def remove_memory(self, memory_id: UUID) -> None:
        """Remove a memory node and its connections.

        Args:
            memory_id: The memory ID to remove.
        """
        if memory_id in self._nodes:
            for neighbor in self._nodes[memory_id]:
                self._relations.pop((memory_id, neighbor), None)

            for from_id, neighbors in self._nodes.items():
                if memory_id in neighbors:
                    neighbors.remove(memory_id)
                    self._relations.pop((from_id, memory_id), None)

            del self._nodes[memory_id]

        for entity, memory_ids in self._entities.items():
            memory_ids.discard(memory_id)

    def extract_entities(self, content: str) -> list[str]:
        """Extract potential entities from content.

        Supports English capitalized phrases and Chinese text inside quotes.

        Args:
            content: The text content.

        Returns:
            List of extracted entity strings.
        """
        import re

        entities = []
        # English Capitalized Phrases
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
        entities.extend(capitalized)

        # Chinese content inside specific quotes: 『』 or 「」 or ""
        chinese_quoted = re.findall(r'[『「"]([^『』「"」]+)[』」"]', content)
        entities.extend(chinese_quoted)

        # Common Chinese keywords (if needed, but quoting is more precise for this engine)
        
        return list(set(entities))
