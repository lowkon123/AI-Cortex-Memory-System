"""Multi-factor scoring for memory ranking.

This module implements the ranking algorithm that scores memories
based on similarity, recency, importance, and access frequency.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from ..models import MemoryNode


class MemoryRanker:
    """Multi-factor ranking algorithm for memory retrieval.

    Scores memories using a weighted combination of:
    - Semantic similarity (via vector distance)
    - Recency (time since last access/update)
    - Importance (base importance + reinforcement boost)
    - Access frequency (how often the memory is used)
    """

    DEFAULT_WEIGHTS = {
        "similarity": 0.4,
        "recency": 0.2,
        "importance": 0.25,
        "frequency": 0.15,
    }

    def __init__(self, weights: Optional[dict[str, float]] = None):
        """Initialize the ranker with optional custom weights.

        Args:
            weights: Optional custom weight dictionary.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS

    def score_memory(
        self,
        memory: MemoryNode,
        query_vector: Optional[list[float]] = None,
        now: Optional[datetime] = None,
    ) -> float:
        """Calculate the composite score for a single memory.

        Args:
            memory: The memory node to score.
            query_vector: Optional query vector for similarity scoring.
            now: Optional current time for recency calculation.

        Returns:
            Composite score between 0.0 and 1.0.
        """
        now = now or datetime.utcnow()

        similarity_score = self._score_similarity(memory, query_vector)
        recency_score = self._score_recency(memory, now)
        importance_score = self._score_importance(memory)
        frequency_score = self._score_frequency(memory)

        return (
            self.weights["similarity"] * similarity_score
            + self.weights["recency"] * recency_score
            + self.weights["importance"] * importance_score
            + self.weights["frequency"] * frequency_score
        )

    def rank_memories(
        self,
        memories: list[MemoryNode],
        query_vector: Optional[list[float]] = None,
        limit: int = 20,
    ) -> list[tuple[MemoryNode, float]]:
        """Rank and sort a list of memories by composite score.

        Args:
            memories: List of memory nodes to rank.
            query_vector: Optional query vector for similarity.
            limit: Maximum number of results to return.

        Returns:
            Sorted list of (memory, score) tuples, highest score first.
        """
        now = datetime.utcnow()
        scored = [
            (memory, self.score_memory(memory, query_vector, now))
            for memory in memories
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _score_similarity(
        self, memory: MemoryNode, query_vector: Optional[list[float]]
    ) -> float:
        """Score based on semantic similarity to query.

        Args:
            memory: The memory to score.
            query_vector: The query embedding vector.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if query_vector is None or memory.embedding is None:
            return 0.5  # Neutral when no comparison possible

        import numpy as np

        q = np.array(query_vector, dtype=np.float32)
        m = np.array(memory.embedding, dtype=np.float32)

        q = q / np.linalg.norm(q)
        m = m / np.linalg.norm(m)

        cosine = np.dot(q, m)
        return float((cosine + 1) / 2)  # Normalize to [0, 1]

    def _score_recency(
        self, memory: MemoryNode, now: datetime
    ) -> float:
        """Score based on how recently the memory was accessed.

        Uses exponential decay with a half-life of 7 days.

        Args:
            memory: The memory to score.
            now: Current time reference.

        Returns:
            Recency score between 0.0 and 1.0.
        """
        last_access = memory.last_accessed or memory.updated_at
        age = (now - last_access).total_seconds()
        half_life = timedelta(days=7).total_seconds()
        return float(2 ** (-age / half_life))

    def _score_importance(self, memory: MemoryNode) -> float:
        """Score based on importance including reinforcement boost.

        Args:
            memory: The memory to score.

        Returns:
            Importance score between 0.0 and 1.0.
        """
        base = memory.importance
        boost = memory.importance_boost
        combined = base + boost
        return min(1.0, max(0.0, combined))

    def _score_frequency(self, memory: MemoryNode) -> float:
        """Score based on access frequency.

        Uses logarithmic scaling to prevent dominance by old memories.

        Args:
            memory: The memory to score.

        Returns:
            Frequency score between 0.0 and 1.0.
        """
        import math

        count = memory.access_count
        if count == 0:
            return 0.0
        return float(min(1.0, math.log2(count + 1) / 10))
