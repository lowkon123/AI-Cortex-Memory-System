"""Neural decay and pruning logic for memory management.

This module implements the "forgetting" mechanism that naturally
decays memory importance over time and prunes low-value memories.
"""

from datetime import datetime, timedelta
from typing import Optional

from ..models import MemoryNode, MemoryStatus


class MemoryForgetting:
    """Neural decay and pruning for memory lifecycle management.

    Implements exponential decay of importance_boost and can mark
    memories for archival or permanent deletion.
    """

    def __init__(
        self,
        decay_factor: float = 0.9,
        prune_threshold: float = 0.05,
        stale_days: int = 30,
    ):
        """Initialize the forgetting engine.

        Args:
            decay_factor: Multiplier applied each decay cycle (0.0 to 1.0).
            prune_threshold: Below this importance, memory is pruned.
            stale_days: Days without access before memory is considered stale.
        """
        self.decay_factor = decay_factor
        self.prune_threshold = prune_threshold
        self.stale_days = stale_days

    def apply_decay(self, memory: MemoryNode) -> MemoryNode:
        """Apply one cycle of neural decay to a memory.

        Reduces the importance_boost and slightly decays base importance.

        Args:
            memory: The memory to decay.

        Returns:
            The memory with decayed values.
        """
        memory.importance_boost *= self.decay_factor
        if memory.importance_boost < 0.01:
            memory.importance_boost = 0.0

        memory.importance = max(0.1, memory.importance * 0.995)
        memory.updated_at = datetime.utcnow()
        return memory

    def should_prune(self, memory: MemoryNode) -> bool:
        """Determine if a memory should be pruned.

        Args:
            memory: The memory to evaluate.

        Returns:
            True if the memory should be removed.
        """
        effective_importance = memory.importance + memory.importance_boost
        return effective_importance < self.prune_threshold

    def is_stale(self, memory: MemoryNode, now: Optional[datetime] = None) -> bool:
        """Check if a memory has become stale from lack of access.

        Args:
            memory: The memory to check.
            now: Optional current time reference.

        Returns:
            True if the memory is stale.
        """
        now = now or datetime.utcnow()
        cutoff = now - timedelta(days=self.stale_days)

        last_check = memory.last_accessed or memory.updated_at
        return last_check < cutoff

    def get_new_status(self, memory: MemoryNode) -> MemoryStatus:
        """Determine the appropriate status for a memory.

        Args:
            memory: The memory to evaluate.

        Returns:
            Recommended MemoryStatus for the memory.
        """
        if self.should_prune(memory):
            return MemoryStatus.FORGOTTEN
        elif self.is_stale(memory):
            return MemoryStatus.ARCHIVED
        return memory.status

    def process_batch(self, memories: list[MemoryNode]) -> list[MemoryNode]:
        """Process a batch of memories for decay and pruning.

        Args:
            memories: List of memories to process.

        Returns:
            List of memories that were modified.
        """
        modified = []
        for memory in memories:
            if memory.status not in (MemoryStatus.ARCHIVED, MemoryStatus.FORGOTTEN):
                self.apply_decay(memory)
                new_status = self.get_new_status(memory)
                if new_status != memory.status:
                    memory.status = new_status
                modified.append(memory)
        return modified

    def schedule_pruning(
        self, memories: list[MemoryNode], dry_run: bool = True
    ) -> list[MemoryNode]:
        """Identify memories scheduled for pruning.

        Args:
            memories: List of memories to evaluate.
            dry_run: If True, only return candidates without modifying.

        Returns:
            List of memories marked for pruning.
        """
        candidates = [m for m in memories if self.should_prune(m)]
        if not dry_run:
            for memory in candidates:
                memory.status = MemoryStatus.FORGOTTEN
        return candidates
