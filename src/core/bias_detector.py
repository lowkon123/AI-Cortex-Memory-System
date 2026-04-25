"""Bias Detector — Memory bias audit system.

Fixes #48: AI decisions can be contaminated by historical memories, 
forming "cognitive biases".

For example, if most memories about a certain technology are negative 
(due to early issues), the AI might continue to be biased against it 
even after the situation has improved.

This module provides:
1. Bias distribution analysis (sentiment, importance)
2. Memory diversity scoring (avoiding Echo Chamber effect)
3. Conflicting memory identification
4. Bias warning markers (alerting the AI in high-bias scenarios)
"""

from __future__ import annotations

from collections import Counter
from typing import Optional
from uuid import UUID

from ..models import MemoryKind, MemoryNode, MemoryStatus


class BiasReport:
    """Results of a memory bias audit."""

    def __init__(
        self,
        total_analyzed: int,
        sentiment_distribution: dict[str, float],
        diversity_score: float,
        conflict_pairs: list[tuple[UUID, UUID]],
        dominant_concepts: list[str],
        bias_warnings: list[str],
    ):
        """Initialize BiasReport.

        Args:
            total_analyzed: Total number of memories analyzed.
            sentiment_distribution: Distribution of sentiment polarities.
            diversity_score: Score representing memory diversity (0.0 to 1.0).
            conflict_pairs: List of conflicting memory ID pairs.
            dominant_concepts: Most frequent concept tags.
            bias_warnings: List of specific bias warning messages.
        """
        self.total_analyzed = total_analyzed
        self.sentiment_distribution = sentiment_distribution
        self.diversity_score = diversity_score
        self.conflict_pairs = conflict_pairs
        self.dominant_concepts = dominant_concepts
        self.bias_warnings = bias_warnings

    @property
    def is_biased(self) -> bool:
        """Determine if the memory pool has significant bias."""
        return len(self.bias_warnings) > 0

    @property
    def bias_level(self) -> str:
        """Bias level rating."""
        n = len(self.bias_warnings)
        if n == 0:
            return "healthy"
        if n <= 1:
            return "mild"
        if n <= 3:
            return "moderate"
        return "severe"

    def summary(self) -> str:
        """Generate a bias audit summary (can be injected into System Prompt)."""
        if not self.is_biased:
            return "[Memory Health] Good: No significant cognitive bias detected."

        lines = [f"[Cognitive Bias Warning] Level: {self.bias_level.upper()}"]
        for w in self.bias_warnings:
            lines.append(f"  ⚠️ {w}")
        lines.append(f"Diversity Score: {self.diversity_score:.2f} / 1.0 (Higher is more balanced)")
        return "\n".join(lines)


class BiasDetector:
    """Analyzes the memory pool for systemic cognitive biases.

    Bias Types:
    - Sentiment Bias: Over-concentration of one sentiment (positive/negative).
    - Concept Bias: A few concepts occupy most memory resources (Echo Chamber).
    - Conflict Bias: Direct contradictions between high-importance memories.
    - Recency/Anchoring Bias: Old memories dominate new information.
    """

    def __init__(
        self,
        sentiment_skew_threshold: float = 0.75,
        concept_dominance_threshold: float = 0.50,
        diversity_min_threshold: float = 0.30,
    ):
        """Initialize BiasDetector.

        Args:
            sentiment_skew_threshold: Ratio above which sentiment is skewed.
            concept_dominance_threshold: Concept dominance ratio threshold.
            diversity_min_threshold: Minimum diversity score before warning.
        """
        self.sentiment_skew_threshold = sentiment_skew_threshold
        self.concept_dominance_threshold = concept_dominance_threshold
        self.diversity_min_threshold = diversity_min_threshold

    def analyze(
        self,
        memories: list[MemoryNode],
        topic: Optional[str] = None,
    ) -> BiasReport:
        """Audit a list of memories for bias.

        Args:
            memories: List of memory nodes to analyze.
            topic: Optional topic filter.

        Returns:
            A BiasReport object.
        """
        if topic:
            memories = [m for m in memories if topic.lower() in m.content.lower() or topic.lower() in " ".join(m.concept_tags).lower()]

        active = [m for m in memories if m.status == MemoryStatus.ACTIVE]
        if not active:
            return BiasReport(
                total_analyzed=0,
                sentiment_distribution={},
                diversity_score=1.0,
                conflict_pairs=[],
                dominant_concepts=[],
                bias_warnings=[],
            )

        warnings: list[str] = []

        # 1. Sentiment Distribution Analysis
        sentiment_dist = self._analyze_sentiment(active)
        dominant_sentiment = max(sentiment_dist, key=sentiment_dist.get, default=None)
        if dominant_sentiment and sentiment_dist.get(dominant_sentiment, 0) > self.sentiment_skew_threshold:
            warnings.append(
                f"Sentiment Bias: {dominant_sentiment} sentiment at {sentiment_dist[dominant_sentiment]:.0%}, "
                f"which may skew evaluations."
            )

        # 2. Concept Diversity Analysis
        diversity_score = self._compute_diversity(active)
        if diversity_score < self.diversity_min_threshold:
            warnings.append(
                f"Memory Homogenization: Diversity score {diversity_score:.2f}, "
                f"indicating a potential Echo Chamber effect."
            )

        # 3. Dominant Concept Analysis
        dominant_concepts = self._find_dominant_concepts(active)
        if dominant_concepts:
            top_concept, top_ratio = dominant_concepts[0]
            if top_ratio > self.concept_dominance_threshold:
                warnings.append(
                    f"Concept Dominance: '{top_concept}' occupies {top_ratio:.0%} of memories, "
                    f"potentially over-dominating AI decisions."
                )

        # 4. Conflicting Memory Identification
        conflict_pairs = self._find_conflict_pairs(active)
        if len(conflict_pairs) > 3:
            warnings.append(
                f"Decision Conflict: {len(conflict_pairs)} pairs of contradictory memories found, "
                f"making judgments on related topics unstable."
            )

        # 5. Anchoring Bias
        anchoring_issue = self._check_anchoring_bias(active)
        if anchoring_issue:
            warnings.append(anchoring_issue)

        return BiasReport(
            total_analyzed=len(active),
            sentiment_distribution=sentiment_dist,
            diversity_score=diversity_score,
            conflict_pairs=conflict_pairs,
            dominant_concepts=[c for c, _ in dominant_concepts[:5]],
            bias_warnings=warnings,
        )

    def _analyze_sentiment(self, memories: list[MemoryNode]) -> dict[str, float]:
        """Calculate sentiment polarity distribution."""
        counts: Counter = Counter()
        for m in memories:
            sentiment = m.sentiment or "neutral"
            counts[sentiment] += 1
        total = len(memories) or 1
        return {k: round(v / total, 3) for k, v in counts.items()}

    def _compute_diversity(self, memories: list[MemoryNode]) -> float:
        """Compute concept diversity using normalized Shannon Entropy."""
        import math

        all_tags: list[str] = []
        for m in memories:
            all_tags.extend(m.concept_tags[:3])

        if not all_tags:
            return 0.5

        freq = Counter(all_tags)
        total = sum(freq.values())
        entropy = -sum((c / total) * math.log2(c / total) for c in freq.values())

        # Max entropy (uniform distribution)
        max_entropy = math.log2(len(freq)) if len(freq) > 1 else 1.0
        return round(entropy / max_entropy, 3) if max_entropy > 0 else 0.0

    def _find_dominant_concepts(
        self, memories: list[MemoryNode]
    ) -> list[tuple[str, float]]:
        """Identify dominant concept tags and their ratios."""
        all_tags: list[str] = []
        for m in memories:
            all_tags.extend(m.concept_tags)

        if not all_tags:
            return []

        freq = Counter(all_tags)
        total = len(all_tags)
        return [
            (tag, round(count / total, 3))
            for tag, count in freq.most_common(10)
        ]

    def _find_conflict_pairs(
        self, memories: list[MemoryNode]
    ) -> list[tuple[UUID, UUID]]:
        """Identify marked conflicting memory pairs."""
        pairs: list[tuple[UUID, UUID]] = []
        for m in memories:
            if m.conflict_with:
                pair = tuple(sorted([str(m.id), str(m.conflict_with)]))
                if pair not in [tuple(sorted([str(a), str(b)])) for a, b in pairs]:
                    pairs.append((m.id, m.conflict_with))
        return pairs

    def _check_anchoring_bias(self, memories: list[MemoryNode]) -> Optional[str]:
        """Check if old memories hold excessive importance (Anchoring Bias)."""
        from datetime import timedelta
        from ..models import utc_now

        now = utc_now()
        old_threshold = now - timedelta(days=90)

        old_high_importance = [
            m for m in memories
            if m.created_at < old_threshold
            and (m.importance + m.importance_boost) > 0.8
        ]
        ratio = len(old_high_importance) / len(memories) if memories else 0

        if ratio > 0.4:
            return (
                f"Anchoring Bias: {ratio:.0%} of high-importance memories haven't been updated "
                f"in over 90 days, potentially hindering new information."
            )
        return None

    def get_bias_injection(self, memories: list[MemoryNode], topic: Optional[str] = None) -> str:
        """Generate bias warning text for System Prompt injection."""
        report = self.analyze(memories, topic=topic)
        if not report.is_biased:
            return ""
        return "\n" + report.summary() + "\n"
