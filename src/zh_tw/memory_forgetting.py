"""Forgetting and consolidation rules for memory maintenance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Optional

from ..models import MemoryNode, MemoryStatus, utc_now


class MemoryForgetting:
    """Apply human-like decay, archiving, and forgetting decisions."""

    def __init__(
        self,
        decay_factor: float = 0.9,
        prune_threshold: float = 0.05,
        stale_days: int = 30,
    ):
        self.decay_factor = decay_factor
        self.prune_threshold = prune_threshold
        self.stale_days = stale_days

    def apply_decay(self, memory: MemoryNode) -> MemoryNode:
        memory.importance_boost *= self.decay_factor
        if memory.importance_boost < 0.01:
            memory.importance_boost = 0.0

        memory.importance = max(0.08, memory.importance * 0.997)
        memory.emotional_weight = max(0.0, memory.emotional_weight * 0.995)
        memory.activation_score = max(
            0.0,
            memory.activation_score * self.decay_factor,
        )
        memory.updated_at = utc_now()
        return memory

    def should_prune(self, memory: MemoryNode) -> bool:
        effective_importance = (
            memory.importance
            + memory.importance_boost
            + (memory.confidence * 0.05)
            + (memory.success_count * 0.01)
        )
        return effective_importance < self.prune_threshold

    def is_stale(self, memory: MemoryNode, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        cutoff = now - timedelta(days=self.stale_days)
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
        if memory.status in (MemoryStatus.FORGOTTEN,):
            return False
        if len(memory.content) < 160:
            return False
        if memory.consolidation_count >= 6:
            return False
        return memory.access_count >= 2 or memory.importance >= 0.7

    def get_new_status(self, memory: MemoryNode) -> MemoryStatus:
        if self.should_prune(memory):
            return MemoryStatus.FORGOTTEN
        if self.is_stale(memory):
            return MemoryStatus.ARCHIVED
        if memory.summary_l0 and memory.summary_l1 and self.should_consolidate(memory):
            return MemoryStatus.COMPRESSED
        return MemoryStatus.ACTIVE

    def process_batch(self, memories: list[MemoryNode]) -> list[MemoryNode]:
        modified = []
        for memory in memories:
            if memory.status == MemoryStatus.FORGOTTEN:
                continue

            self.apply_decay(memory)
            if self.should_consolidate(memory):
                memory.consolidate()

            memory.status = self.get_new_status(memory)
            modified.append(memory)
        return modified

    def schedule_pruning(
        self, memories: list[MemoryNode], dry_run: bool = True
    ) -> list[MemoryNode]:
        candidates = [m for m in memories if self.should_prune(m)]
        if not dry_run:
            for memory in candidates:
                memory.status = MemoryStatus.FORGOTTEN
        return candidates
