"""Forgetting and consolidation rules for memory maintenance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Optional

from ..models import MemoryKind, MemoryNode, MemoryStatus, utc_now


class MemoryForgetting:
    """Apply human-like decay, archiving, and forgetting decisions."""

    def __init__(
        self,
        decay_factor: float = 0.9,
        prune_threshold: float = 0.05,
        stale_days: int = 30,
    ):
        """Initialize the forgetting mechanism with tuning parameters.

        Args:
            decay_factor: Factor applied to activation and importance boost.
            prune_threshold: Importance score below which a memory is deleted.
            stale_days: Default days after which an inactive memory is archived.
        """
        self.decay_factor = decay_factor
        self.prune_threshold = prune_threshold
        self.stale_days = stale_days

    def apply_decay(self, memory: MemoryNode) -> MemoryNode:
        """Apply cognitive decay to a memory node based on its type."""
        # Structured facts and concepts decay much slower (L2 Long-term)
        decay_rate = self.decay_factor
        if memory.memory_kind in (MemoryKind.SEMANTIC,):
            decay_rate = 0.99  # Very stable
        
        memory.importance_boost *= decay_rate
        if memory.importance_boost < 0.01:
            memory.importance_boost = 0.0

        # Base importance also decays slowly
        memory.importance = max(0.08, memory.importance * (0.999 if memory.memory_kind == MemoryKind.SEMANTIC else 0.997))
        memory.emotional_weight = max(0.0, memory.emotional_weight * 0.995)
        memory.activation_score = max(
            0.0,
            memory.activation_score * decay_rate,
        )
        memory.updated_at = utc_now()
        return memory

    def should_prune(self, memory: MemoryNode) -> bool:
        """Determine if a memory node should be permanently deleted."""
        effective_importance = (
            memory.importance
            + memory.importance_boost
            + (memory.confidence * 0.05)
            + (memory.success_count * 0.01)
        )
        return effective_importance < self.prune_threshold

    def is_stale(self, memory: MemoryNode, now: Optional[datetime] = None) -> bool:
        """Check if a memory has been inactive for too long."""
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
            
        # Support TTL (Time-To-Live) from metadata
        ttl_days = memory.metadata.get("ttl_days")
        effective_stale_days = ttl_days if ttl_days is not None else self.stale_days
        
        cutoff = now - timedelta(days=effective_stale_days)
        last_touch = (
            memory.last_reinforced
            or memory.last_accessed
            or memory.last_consolidated
            or memory.updated_at
        )
        if last_touch.tzinfo is None:
            last_touch = last_touch.replace(tzinfo=UTC)
        else:
            last_touch = last_touch.astimezone(UTC)
        return last_touch < cutoff

    def should_consolidate(self, memory: MemoryNode) -> bool:
        """Determine if a memory node reached enough usage for abstraction/summarization."""
        if memory.status in (MemoryStatus.FORGOTTEN,):
            return False
        if len(memory.content) < 160:
            return False
        if memory.consolidation_count >= 6:
            return False
        return memory.access_count >= 2 or memory.importance >= 0.7

    def get_new_status(self, memory: MemoryNode) -> MemoryStatus:
        """Determine the next lifecycle status for a memory node."""
        if self.should_prune(memory):
            return MemoryStatus.FORGOTTEN
        if self.is_stale(memory):
            return MemoryStatus.ARCHIVED
        if memory.summary_l0 and memory.summary_l1 and self.should_consolidate(memory):
            return MemoryStatus.COMPRESSED
        return MemoryStatus.ACTIVE

    def process_batch(self, memories: list[MemoryNode]) -> list[MemoryNode]:
        """Process a list of memories for decay and status updates."""
        modified = []
        for memory in memories:
            if memory.status == MemoryStatus.FORGOTTEN:
                continue

            self.apply_decay(memory)
            if self.should_consolidate(memory):
                memory.consolidation_count += 1
                memory.last_consolidated = utc_now()

            memory.status = self.get_new_status(memory)
            modified.append(memory)
        return modified

    def schedule_pruning(
        self, memories: list[MemoryNode], dry_run: bool = True
    ) -> list[MemoryNode]:
        """Find candidates for pruning and optionally update their status."""
        candidates = [m for m in memories if self.should_prune(m)]
        if not dry_run:
            for memory in candidates:
                memory.status = MemoryStatus.FORGOTTEN
        return candidates
