"""Timeline Snapshot — System state snapshots and timeline management.

Fixes #38: Systems lack clear timeline snapshots of the current state, 
making it hard for AI to understand "what is the current truth".

This module generates "Cognitive Snapshots" periodically or on demand, 
recording current:
- Top importance memory summaries
- Active concept tag distribution
- Recent major events

This allows the AI to quickly orient its current cognitive state at 
the beginning of a conversation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from ..models import MemoryKind, MemoryNode, MemorySource, MemoryStatus, utc_now


class TimelineSnapshot:
    """Generates and manages system cognitive state snapshots.

    A snapshot is a special MemoryNode (kind=FACT, source=SYSTEM) 
    whose content summarizes the current cognitive state, with 
    structured stats in metadata.
    """

    SNAPSHOT_TAG = "__timeline_snapshot__"

    def __init__(
        self,
        persona: str = "default",
        snapshot_interval_hours: int = 24,
    ):
        """Initialize TimelineSnapshot.

        Args:
            persona: Persona namespace for snapshots.
            snapshot_interval_hours: Interval for automatic snapshots.
        """
        self.persona = persona
        self.snapshot_interval_hours = snapshot_interval_hours
        self._last_snapshot_at: Optional[datetime] = None

    async def capture(self, store) -> MemoryNode:
        """Generate current cognitive state snapshot and store it.

        Args:
            store: MemoryStore instance.

        Returns:
            The stored snapshot MemoryNode.
        """
        # Fetch active memories
        all_memories = await store.list_by_persona(self.persona, limit=500)
        active = [m for m in all_memories if m.status == MemoryStatus.ACTIVE]

        # Compute stats
        stats = self._compute_stats(active)

        # Generate summary text
        summary = self._format_summary(stats)

        # Create snapshot node
        snapshot_node = MemoryNode(
            content=summary,
            summary_l1=f"System Snapshot @ {utc_now().strftime('%Y-%m-%d %H:%M UTC')}",
            summary_l0="Cognitive State Snapshot",
            importance=0.8,
            memory_kind=MemoryKind.SEMANTIC,
            source_type=MemorySource.SYSTEM,
            persona=self.persona,
            concept_tags=[self.SNAPSHOT_TAG],
            metadata={
                "_snapshot": True,
                "_captured_at": utc_now().isoformat(),
                "_stats": stats,
            },
        )

        await store.insert(snapshot_node)
        self._last_snapshot_at = utc_now()
        return snapshot_node

    def _compute_stats(self, memories: list[MemoryNode]) -> dict:
        """Compute structured stats from memory list."""
        if not memories:
            return {"total": 0}

        # Count by kind
        kind_counts: dict[str, int] = {}
        for m in memories:
            kind_counts[m.memory_kind.value] = kind_counts.get(m.memory_kind.value, 0) + 1

        # Top 5 most important
        top_important = sorted(memories, key=lambda m: m.importance + m.importance_boost, reverse=True)[:5]

        # Top 10 active tags
        tag_freq: dict[str, int] = {}
        for m in memories:
            for tag in m.concept_tags:
                tag_freq[tag] = tag_freq.get(tag, 0) + 1
        top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top 5 recent
        recent = sorted(memories, key=lambda m: m.updated_at, reverse=True)[:5]

        return {
            "total": len(memories),
            "kind_distribution": kind_counts,
            "avg_importance": round(
                sum(m.importance for m in memories) / len(memories), 3
            ),
            "avg_confidence": round(
                sum(m.confidence for m in memories) / len(memories), 3
            ),
            "top_important_summaries": [
                m.summary_l0 or m.content[:50] for m in top_important
            ],
            "top_concept_tags": [tag for tag, _ in top_tags],
            "recent_memories": [
                m.summary_l0 or m.content[:50] for m in recent
            ],
        }

    def _format_summary(self, stats: dict) -> str:
        """Format stats into human-readable summary."""
        if not stats.get("total"):
            return "System Snapshot: Memory store is currently empty."

        lines = [
            f"[System Cognitive Snapshot] @ {utc_now().strftime('%Y-%m-%d %H:%M UTC')}",
            f"Total Memories: {stats['total']}",
            f"Avg Importance: {stats.get('avg_importance', 0):.2f} | Avg Confidence: {stats.get('avg_confidence', 0):.2f}",
            "",
        ]

        # Distribution
        kind_dist = stats.get("kind_distribution", {})
        if kind_dist:
            dist_str = " | ".join(f"{k}: {v}" for k, v in kind_dist.items())
            lines.append(f"Memory Kind Distribution: {dist_str}")

        # Core concepts
        top_tags = stats.get("top_concept_tags", [])
        if top_tags:
            lines.append(f"Core Concepts: {', '.join(top_tags[:8])}")

        # Top Important
        top_summaries = stats.get("top_important_summaries", [])
        if top_summaries:
            lines.append("")
            lines.append("Most Important Knowledge:")
            for i, s in enumerate(top_summaries, 1):
                lines.append(f"  {i}. {s}")

        # Recent activities
        recent = stats.get("recent_memories", [])
        if recent:
            lines.append("")
            lines.append("Recent Memories:")
            for s in recent[:3]:
                lines.append(f"  • {s}")

        return "\n".join(lines)

    def should_capture(self) -> bool:
        """Check if it's time for an automatic snapshot."""
        if self._last_snapshot_at is None:
            return True
        from datetime import timedelta
        elapsed = utc_now() - self._last_snapshot_at
        return elapsed.total_seconds() >= self.snapshot_interval_hours * 3600

    async def get_latest_snapshot(self, store) -> Optional[MemoryNode]:
        """Fetch the latest snapshot from store."""
        memories = await store.list_by_concepts(
            [self.SNAPSHOT_TAG], limit=1
        )
        return memories[0] if memories else None

    async def auto_capture(self, store) -> Optional[MemoryNode]:
        """Automatically capture snapshot if due."""
        if self.should_capture():
            return await self.capture(store)
        return None

    async def get_snapshot_history(self, store, limit: int = 10) -> list[MemoryNode]:
        """Fetch snapshot history."""
        memories = await store.list_by_concepts([self.SNAPSHOT_TAG], limit=limit)
        return sorted(memories, key=lambda m: m.created_at, reverse=True)
