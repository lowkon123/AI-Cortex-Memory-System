"""Epistemic Marker — Epistemological labeling system.

Fixes #8: Clearly distinguish between "Fact/Inference/Belief/Hypothesis" 
in memories, preventing the AI from citing speculative conclusions 
as hard facts.

Each memory now carries an `epistemic_type` which affects:
- Ranking weight (Facts > Inferences > Hypotheses)
- Conflict detection sensitivity (Fact contradiction > Opinion contradiction)
- Confidence score calculation boundaries
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from ..models import MemoryNode


class EpistemicType(str, Enum):
    """Epistemological types for memories."""

    FACT = "fact"
    """Verified objective fact. e.g., 'Python is an interpreted language'."""

    INFERENCE = "inference"
    """Logical deduction based on existing facts. e.g., 'Based on code, user prefers functional style'."""

    BELIEF = "belief"
    """Subjective view or preference of the user. e.g., 'User believes TypeScript is better than JavaScript'."""

    HYPOTHESIS = "hypothesis"
    """Unverified assumption. e.g., 'Maybe a memory leak caused the crash'."""

    SPECULATION = "speculation"
    """Pure speculation with little to no factual basis. e.g., 'Perhaps the user wants to switch frameworks?'."""


# Confidence caps for each epistemic type (prevents high trust in speculation)
EPISTEMIC_CONFIDENCE_CAPS: dict[EpistemicType, float] = {
    EpistemicType.FACT: 1.0,
    EpistemicType.INFERENCE: 0.85,
    EpistemicType.BELIEF: 0.75,
    EpistemicType.HYPOTHESIS: 0.60,
    EpistemicType.SPECULATION: 0.40,
}

# Ranking weight multipliers for each type
EPISTEMIC_RANK_MULTIPLIERS: dict[EpistemicType, float] = {
    EpistemicType.FACT: 1.0,
    EpistemicType.INFERENCE: 0.90,
    EpistemicType.BELIEF: 0.80,
    EpistemicType.HYPOTHESIS: 0.65,
    EpistemicType.SPECULATION: 0.45,
}


class EpistemicMarker:
    """Labels and manages epistemological types for memory nodes."""

    METADATA_KEY = "_epistemic_type"

    def mark(
        self,
        node: MemoryNode,
        epistemic_type: EpistemicType,
        evidence: Optional[str] = None,
    ) -> MemoryNode:
        """Mark a memory node with an epistemic type.

        Args:
            node: Node to label.
            epistemic_type: The epistemic type to apply.
            evidence: Optional supporting info (e.g., which memory supported this inference).

        Returns:
            The labeled node (modified in-place).
        """
        node.metadata[self.METADATA_KEY] = epistemic_type.value

        # Apply confidence cap
        cap = EPISTEMIC_CONFIDENCE_CAPS[epistemic_type]
        node.confidence = min(node.confidence, cap)

        if evidence:
            node.metadata["_epistemic_evidence"] = evidence

        return node

    def get_type(self, node: MemoryNode) -> EpistemicType:
        """Read epistemic type from a node. Defaults to INFERENCE."""
        raw = node.metadata.get(self.METADATA_KEY, EpistemicType.INFERENCE.value)
        try:
            return EpistemicType(raw)
        except ValueError:
            return EpistemicType.INFERENCE

    def get_rank_multiplier(self, node: MemoryNode) -> float:
        """Get the confidence multiplier for ranking."""
        etype = self.get_type(node)
        return EPISTEMIC_RANK_MULTIPLIERS.get(etype, 0.75)

    def apply_to_score(self, node: MemoryNode, base_score: float) -> float:
        """Apply epistemic multiplier to base ranking score."""
        return base_score * self.get_rank_multiplier(node)

    def is_reliable(self, node: MemoryNode, min_confidence: float = 0.65) -> bool:
        """Determine if a memory is reliable enough for decision support."""
        etype = self.get_type(node)
        if etype in (EpistemicType.SPECULATION, EpistemicType.HYPOTHESIS):
            return False
        return node.confidence >= min_confidence

    def infer_from_source(self, node: MemoryNode) -> EpistemicType:
        """Heuristically infer epistemic type based on source and kind."""
        from ..models import MemoryKind, MemorySource

        if node.source_type == MemorySource.INFERRED:
            return EpistemicType.INFERENCE
        if node.memory_kind == MemoryKind.SEMANTIC:
            return EpistemicType.FACT
        if node.memory_kind == MemoryKind.CONCEPT:
            return EpistemicType.INFERENCE
        if node.memory_kind in (MemoryKind.EPISODIC, MemoryKind.WORKING):
            return EpistemicType.BELIEF
        return EpistemicType.INFERENCE

    def auto_mark(self, node: MemoryNode) -> MemoryNode:
        """Automatically assign epistemic label based on source and kind."""
        inferred_type = self.infer_from_source(node)
        return self.mark(node, inferred_type)

    def filter_reliable(
        self, nodes: list[MemoryNode], min_confidence: float = 0.65
    ) -> list[MemoryNode]:
        """Filter reliable memories from a list (excl. low-confidence speculation)."""
        return [n for n in nodes if self.is_reliable(n, min_confidence)]

    def summarize(self, nodes: list[MemoryNode]) -> dict[str, int]:
        """Statistic distribution of epistemic types in a list."""
        counts: dict[str, int] = {t.value: 0 for t in EpistemicType}
        for node in nodes:
            etype = self.get_type(node)
            counts[etype.value] += 1
        return counts
