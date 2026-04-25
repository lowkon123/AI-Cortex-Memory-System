"""Index Maintenance — Long-term health of memory indices.

Fixes #20: Retrieval quality degrades as the memory pool grows.

As the memory pool expands, issues like vector index fragmentation, 
stale statistics, and inaccurate query plans accumulate, 
leading to slower searches and poorer recall quality.

This module provides periodic index maintenance functions:
- PostgreSQL VACUUM / ANALYZE (Update query planner statistics)
- Vector Index Rebuild (Resolve fragmentation)
- Orphan Node Cleanup (Remove junk nodes with no embeddings)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from ..models import MemoryStatus, utc_now


class IndexMaintenance:
    """Manages the long-term health of memory store indices.

    Fixes #20: Long-term retrieval quality degradation.

    Recommended Schedule:
    - ANALYZE: Every 6 hours (lightweight, tracks Sleep Cycle)
    - VACUUM: Every 24 hours (medium, during low load)
    - Reindex: Every 7 days (heavy, only if pool > 10k nodes)
    - Orphan Cleanup: Every 24 hours
    """

    def __init__(
        self,
        analyze_interval_hours: int = 6,
        vacuum_interval_hours: int = 24,
        reindex_interval_days: int = 7,
        orphan_cleanup_interval_hours: int = 24,
    ):
        """Initialize maintenance scheduler with intervals."""
        self.analyze_interval_hours = analyze_interval_hours
        self.vacuum_interval_hours = vacuum_interval_hours
        self.reindex_interval_days = reindex_interval_days
        self.orphan_cleanup_interval_hours = orphan_cleanup_interval_hours

        self._last_analyze: Optional[object] = None
        self._last_vacuum: Optional[object] = None
        self._last_reindex: Optional[object] = None
        self._last_orphan_cleanup: Optional[object] = None

    async def run_analyze(self, pool) -> dict:
        """Run ANALYZE: Update query planner statistics.

        Lightweight operation that should be run frequently.
        Ensures the PostgreSQL query optimizer uses up-to-date data distribution statistics.
        """
        async with pool.acquire() as conn:
            await conn.execute("ANALYZE memories")
            await conn.execute("ANALYZE memory_relations")
        self._last_analyze = utc_now()
        return {"operation": "analyze", "status": "ok", "ran_at": self._last_analyze.isoformat()}

    async def run_vacuum(self, pool) -> dict:
        """Run VACUUM: Reclaim disk space from deleted memories.

        Soft-deleted (FORGOTTEN) memories in Sleep Cycle still occupy space.
        VACUUM cleans up these dead tuples to prevent table bloat.
        """
        async with pool.acquire() as conn:
            # Cannot be executed in a transaction, requires direct connection
            await conn.execute("VACUUM memories")
        self._last_vacuum = utc_now()
        return {"operation": "vacuum", "status": "ok", "ran_at": self._last_vacuum.isoformat()}

    async def run_reindex(self, pool) -> dict:
        """Rebuild vector indices: Resolve fragmentation.

        After many insertions/deletions, the pgvector HNSW index can become fragmented.
        Rebuilding the index restores optimal search performance.
        Uses CONCURRENTLY to avoid blocking online queries.
        """
        async with pool.acquire() as conn:
            # Rebuild vector index (if it exists)
            await conn.execute(
                "REINDEX INDEX CONCURRENTLY IF EXISTS idx_memories_embedding_hnsw"
            )
            # Rebuild FTS index
            await conn.execute(
                "REINDEX INDEX CONCURRENTLY IF EXISTS idx_memories_content_fts"
            )
        self._last_reindex = utc_now()
        return {"operation": "reindex", "status": "ok", "ran_at": self._last_reindex.isoformat()}

    async def cleanup_orphans(self, pool) -> dict:
        """Clean up orphan nodes: Delete forgotten memories with no embeddings.

        Nodes that stay FORGOTTEN for a long time and have no embeddings are junk data.
        Cleaning them improves index efficiency and query speed.
        """
        cutoff = utc_now() - timedelta(days=30)
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM memories
                WHERE status = 'forgotten'
                AND embedding IS NULL
                AND updated_at < $1
                """,
                cutoff,
            )
        deleted_count = int(result.split()[-1]) if result else 0
        self._last_orphan_cleanup = utc_now()
        return {
            "operation": "orphan_cleanup",
            "deleted": deleted_count,
            "status": "ok",
            "ran_at": self._last_orphan_cleanup.isoformat(),
        }

    async def get_health_report(self, pool) -> dict:
        """Generate an index health report.

        Returns:
            Dictionary with table size, index status, dead tuple ratio, etc.
        """
        async with pool.acquire() as conn:
            # Table size
            size_row = await conn.fetchrow(
                "SELECT pg_size_pretty(pg_total_relation_size('memories')) as size"
            )

            # Memory count by status
            status_rows = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM memories GROUP BY status"
            )

            # Dead tuple ratio
            bloat_row = await conn.fetchrow(
                """
                SELECT
                    n_live_tup,
                    n_dead_tup,
                    CASE WHEN n_live_tup > 0
                        THEN round(n_dead_tup::numeric / n_live_tup * 100, 2)
                        ELSE 0
                    END as dead_ratio
                FROM pg_stat_user_tables
                WHERE relname = 'memories'
                """
            )

            # Index sizes
            index_rows = await conn.fetch(
                """
                SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
                FROM pg_indexes
                WHERE tablename = 'memories'
                """
            )

        return {
            "table_size": size_row["size"] if size_row else "unknown",
            "status_counts": {row["status"]: row["cnt"] for row in status_rows},
            "dead_tuple_ratio": (
                f"{bloat_row['dead_ratio']}%" if bloat_row else "unknown"
            ),
            "live_tuples": bloat_row["n_live_tup"] if bloat_row else 0,
            "indexes": [
                {"name": row["indexname"], "size": row["size"]} for row in index_rows
            ],
            "maintenance_schedule": {
                "last_analyze": self._last_analyze.isoformat() if self._last_analyze else None,
                "last_vacuum": self._last_vacuum.isoformat() if self._last_vacuum else None,
                "last_reindex": self._last_reindex.isoformat() if self._last_reindex else None,
            },
        }

    def _is_due(self, last_run, interval_hours: int) -> bool:
        """Check if it's time to run maintenance."""
        if last_run is None:
            return True
        elapsed = utc_now() - last_run
        return elapsed >= timedelta(hours=interval_hours)

    async def run_scheduled_maintenance(self, pool, total_memories: int = 0) -> list[dict]:
        """Automatically run needed maintenance tasks based on schedule.

        Args:
            pool: asyncpg connection pool.
            total_memories: Current total number of memories.

        Returns:
            List of completed maintenance tasks.
        """
        completed_tasks: list[dict] = []

        if self._is_due(self._last_analyze, self.analyze_interval_hours):
            result = await self.run_analyze(pool)
            completed_tasks.append(result)

        if self._is_due(self._last_vacuum, self.vacuum_interval_hours):
            result = await self.run_vacuum(pool)
            completed_tasks.append(result)

        if self._is_due(self._last_orphan_cleanup, self.orphan_cleanup_interval_hours):
            result = await self.cleanup_orphans(pool)
            completed_tasks.append(result)

        # Reindex only for large datasets and according to schedule
        if (
            total_memories > 5000
            and self._is_due(self._last_reindex, self.reindex_interval_days * 24)
        ):
            result = await self.run_reindex(pool)
            completed_tasks.append(result)

        return completed_tasks
