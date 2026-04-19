"""Reinforcement feedback loop for boosting successful memories.

This module tracks which memories were successfully used to solve
LLM tasks and boosts their importance based on utility feedback.
"""

from typing import Optional
from uuid import UUID

from .models import MemoryNode, utc_now


class MemoryFeedback:
    """Reinforcement feedback system for memory utility tracking.

    Monitors which memories contribute to successful task completion
    and applies importance boosts as reinforcement signals.
    """

    def __init__(self, boost_decay: float = 0.95, max_boost: float = 0.5):
        """Initialize the feedback system.

        Args:
            boost_decay: How much boosts decay each cycle (0.0 to 1.0).
            max_boost: Maximum boost amount per successful use.
        """
        self.boost_decay = boost_decay
        self.max_boost = max_boost
        self._feedback_log: list[FeedbackEntry] = []
        self._memory_successes: dict[UUID, int] = {}

    def record_success(
        self,
        memory_ids: list[UUID],
        task_id: str,
        task_success: bool = True,
        boost_amount: Optional[float] = None,
    ) -> dict[UUID, float]:
        """Record successful use of memories in completing a task.

        Args:
            memory_ids: List of memory IDs that contributed.
            task_id: Identifier for the task.
            task_success: Whether the task was successful.
            boost_amount: Optional override for boost amount.

        Returns:
            Dictionary mapping memory IDs to their boost amounts.
        """
        entry = FeedbackEntry(
            task_id=task_id,
            memory_ids=memory_ids,
            timestamp=utc_now(),
            success=task_success,
        )
        self._feedback_log.append(entry)

        boosts = {}
        if task_success:
            for memory_id in memory_ids:
                current = self._memory_successes.get(memory_id, 0)
                self._memory_successes[memory_id] = current + 1

                boost = boost_amount or min(self.max_boost, 0.1 * (current + 1))
                boosts[memory_id] = boost

        return boosts

    def apply_boost(self, memory_id: UUID, amount: float) -> float:
        """Calculate and return the boost amount for a memory.

        Args:
            memory_id: The memory ID.
            amount: The boost amount to apply.

        Returns:
            The actual boost applied (capped at max_boost).
        """
        return min(amount, self.max_boost)

    def reinforce_memory(self, memory: MemoryNode, amount: Optional[float] = None) -> MemoryNode:
        """Apply reinforcement directly to a memory object."""
        applied = min(amount or 0.1, self.max_boost)
        memory.reinforce(applied)
        return memory

    def decay_boosts(self, current_boosts: dict[UUID, float]) -> dict[UUID, float]:
        """Apply decay to current importance boosts.

        Args:
            current_boosts: Dictionary of current boost values.

        Returns:
            Dictionary with decayed boost values.
        """
        return {
            mid: boost * self.boost_decay
            for mid, boost in current_boosts.items()
            if boost * self.boost_decay > 0.01
        }

    def get_success_count(self, memory_id: UUID) -> int:
        """Get the number of successful uses for a memory.

        Args:
            memory_id: The memory ID.

        Returns:
            Number of successful task completions.
        """
        return self._memory_successes.get(memory_id, 0)

    def get_top_performing(self, limit: int = 10) -> list[tuple[UUID, int]]:
        """Get the most successful memories.

        Args:
            limit: Maximum number of results.

        Returns:
            List of (memory_id, success_count) tuples.
        """
        sorted_memories = sorted(
            self._memory_successes.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_memories[:limit]

    def get_feedback_for_memory(self, memory_id: UUID) -> list[FeedbackEntry]:
        """Get all feedback entries for a specific memory.

        Args:
            memory_id: The memory ID.

        Returns:
            List of feedback entries involving this memory.
        """
        return [
            entry
            for entry in self._feedback_log
            if memory_id in entry.memory_ids
        ]

    def clear_log(self) -> None:
        """Clear the feedback log (useful for testing)."""
        self._feedback_log.clear()

    def get_stats(self) -> dict:
        """Get aggregate statistics about feedback.

        Returns:
            Dictionary with feedback statistics.
        """
        total_entries = len(self._feedback_log)
        successful_tasks = sum(1 for e in self._feedback_log if e.success)

        return {
            "total_feedback_entries": total_entries,
            "successful_tasks": successful_tasks,
            "unique_memories_used": len(self._memory_successes),
            "avg_boost": (
                sum(b for b in self._memory_successes.values()) /
                len(self._memory_successes)
                if self._memory_successes else 0
            ),
        }


class FeedbackEntry:
    """A single feedback entry recording memory-task interaction."""

    def __init__(
        self,
        task_id: str,
        memory_ids: list[UUID],
        timestamp: datetime,
        success: bool,
    ):
        """Initialize a feedback entry.

        Args:
            task_id: The task identifier.
            memory_ids: Memories used in the task.
            timestamp: When the feedback was recorded.
            success: Whether the task was successful.
        """
        self.task_id = task_id
        self.memory_ids = memory_ids
        self.timestamp = timestamp
        self.success = success
