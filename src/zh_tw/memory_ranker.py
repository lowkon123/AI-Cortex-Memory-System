"""Dynamic ranking and activation logic for the memory system."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Optional

import numpy as np

from ..models import MemoryKind, MemoryNode


class MemoryRanker:
    """Score memories using similarity plus cognitive activation signals."""

    DEFAULT_WEIGHTS = {
        "similarity": 0.22,
        "recency": 0.14,
        "importance": 0.15,
        "frequency": 0.10,
        "reinforcement": 0.12,
        "emotion": 0.08,
        "confidence": 0.08,
        "persona": 0.05,
        "concept": 0.04,
        "kind": 0.02,
    }

    KIND_PRIOR = {
        MemoryKind.WORKING: 1.0,
        MemoryKind.EPISODIC: 0.8,
        MemoryKind.SEMANTIC: 0.72,
        MemoryKind.PROCEDURAL: 0.68,
    }

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def score_memory(
        self,
        memory: MemoryNode,
        query_vector: Optional[list[float]] = None,
        now: Optional[datetime] = None,
        persona: Optional[str] = None,
        query_tags: Optional[list[str]] = None,
        desired_kinds: Optional[list[MemoryKind]] = None,
    ) -> float:
        breakdown = self.explain_score(
            memory=memory,
            query_vector=query_vector,
            now=now,
            persona=persona,
            query_tags=query_tags,
            desired_kinds=desired_kinds,
        )
        return breakdown["score"]

    def explain_score(
        self,
        memory: MemoryNode,
        query_vector: Optional[list[float]] = None,
        now: Optional[datetime] = None,
        persona: Optional[str] = None,
        query_tags: Optional[list[str]] = None,
        desired_kinds: Optional[list[MemoryKind]] = None,
    ) -> dict[str, float | str | list[str]]:
        now = self._ensure_aware(now or datetime.now(UTC))
        query_tags = query_tags or []
        desired_kinds = desired_kinds or []

        components = {
            "similarity": self._score_similarity(memory, query_vector),
            "recency": self._score_recency(memory, now),
            "importance": self._score_importance(memory),
            "frequency": self._score_frequency(memory),
            "reinforcement": self._score_reinforcement(memory),
            "emotion": self._score_emotion(memory),
            "confidence": self._score_confidence(memory),
            "persona": self._score_persona(memory, persona),
            "concept": self._score_concepts(memory, query_tags),
            "kind": self._score_kind(memory, desired_kinds),
        }

        score = sum(self.weights[name] * value for name, value in components.items())
        score = max(0.0, min(1.0, score))

        top_reasons = sorted(
            components.items(),
            key=lambda item: self.weights[item[0]] * item[1],
            reverse=True,
        )[:3]
        reason_labels = [name for name, _ in top_reasons if _ > 0]

        memory.activation_score = score
        return {
            "score": round(score, 4),
            "reason": " + ".join(reason_labels) if reason_labels else "baseline",
            "concept_tags": list(memory.concept_tags),
            **{name: round(value, 4) for name, value in components.items()},
        }

    def rank_memories(
        self,
        memories: list[MemoryNode],
        query_vector: Optional[list[float]] = None,
        limit: int = 20,
        persona: Optional[str] = None,
        query_tags: Optional[list[str]] = None,
        desired_kinds: Optional[list[MemoryKind]] = None,
    ) -> list[tuple[MemoryNode, float]]:
        now = datetime.now(UTC)
        scored = []
        for memory in memories:
            score = self.score_memory(
                memory,
                query_vector=query_vector,
                now=now,
                persona=persona,
                query_tags=query_tags,
                desired_kinds=desired_kinds,
            )
            scored.append((memory, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def _score_similarity(
        self, memory: MemoryNode, query_vector: Optional[list[float]]
    ) -> float:
        if query_vector is None or memory.embedding is None:
            return 0.5

        q = np.array(query_vector, dtype=np.float32)
        m = np.array(memory.embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        m_norm = np.linalg.norm(m)
        if q_norm == 0 or m_norm == 0:
            return 0.5

        cosine = float(np.dot(q / q_norm, m / m_norm))
        return max(0.0, min(1.0, (cosine + 1) / 2))

    def _score_recency(self, memory: MemoryNode, now: datetime) -> float:
        last_touch = self._ensure_aware(
            (
            memory.last_reinforced
            or memory.last_accessed
            or memory.last_consolidated
            or memory.updated_at
            )
        )
        age = (now - last_touch).total_seconds()
        half_life = timedelta(days=7).total_seconds()
        return float(2 ** (-age / half_life))

    def _ensure_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _score_importance(self, memory: MemoryNode) -> float:
        return max(0.0, min(1.0, memory.importance + memory.importance_boost))

    def _score_frequency(self, memory: MemoryNode) -> float:
        if memory.access_count <= 0:
            return 0.0
        return float(min(1.0, math.log2(memory.access_count + 1) / 5))

    def _score_reinforcement(self, memory: MemoryNode) -> float:
        if memory.success_count <= 0:
            return 0.0
        return float(min(1.0, math.log2(memory.success_count + 1) / 4))

    def _score_emotion(self, memory: MemoryNode) -> float:
        sentiment_bonus = {
            "mixed": 0.12,
            "positive": 0.05,
            "negative": 0.05,
            "neutral": 0.0,
            None: 0.0,
            "": 0.0,
        }
        return min(1.0, memory.emotional_weight + sentiment_bonus.get(memory.sentiment, 0.0))

    def _score_confidence(self, memory: MemoryNode) -> float:
        return memory.confidence

    def _score_persona(self, memory: MemoryNode, persona: Optional[str]) -> float:
        if not persona:
            return 0.5
        return 1.0 if memory.persona == persona else 0.15

    def _score_concepts(self, memory: MemoryNode, query_tags: list[str]) -> float:
        if not query_tags or not memory.concept_tags:
            return 0.0
        overlap = len(set(query_tags) & set(memory.concept_tags))
        return min(1.0, overlap / max(1, len(set(query_tags))))

    def _score_kind(
        self, memory: MemoryNode, desired_kinds: list[MemoryKind]
    ) -> float:
        base = self.KIND_PRIOR.get(memory.memory_kind, 0.5)
        if desired_kinds and memory.memory_kind in desired_kinds:
            return 1.0
        return base
