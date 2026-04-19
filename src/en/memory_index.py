"""PostgreSQL metadata management for memories.

This module handles metadata indexing and querying,
providing efficient filtering by importance, recency, and access patterns.
"""

import asyncpg
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from ..models import MemoryNode, MemoryStoreConfig, MemoryStatus


class MemoryIndex:
    """Metadata indexing and filtering for Memory objects.

    Provides efficient querying by metadata fields beyond the content itself.
    """

    def __init__(self, config: MemoryStoreConfig):
        """Initialize the memory index with database configuration.

        Args:
            config: Database connection configuration.
        """
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        self._pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            min_size=2,
            max_size=self.config.pool_size,
        )

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()

    async def init_schema(self) -> None:
        """Initialize the metadata index schema with additional indexes."""
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_access_count ON memories(access_count DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
            """)

    async def get_by_importance(
        self, min_importance: float, limit: int = 50
    ) -> list[UUID]:
        """Get memory IDs filtered by minimum importance score.

        Args:
            min_importance: Minimum importance threshold (0.0 to 1.0).
            limit: Maximum number of results.

        Returns:
            List of memory IDs meeting the threshold.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM memories
                WHERE importance + importance_boost >= $1
                AND status = 'active'
                ORDER BY (importance + importance_boost) DESC
                LIMIT $2
                """,
                min_importance,
                limit,
            )
            return [row["id"] for row in rows]

    async def get_recent(self, hours: int = 24, limit: int = 50) -> list[UUID]:
        """Get IDs of recently updated memories.

        Args:
            hours: Number of hours to look back.
            limit: Maximum number of results.

        Returns:
            List of recent memory IDs.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM memories
                WHERE updated_at >= $1
                AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                cutoff,
                limit,
            )
            return [row["id"] for row in rows]

    async def get_frequently_accessed(
        self, min_access_count: int = 5, limit: int = 50
    ) -> list[UUID]:
        """Get IDs of frequently accessed memories.

        Args:
            min_access_count: Minimum access count threshold.
            limit: Maximum number of results.

        Returns:
            List of frequently accessed memory IDs.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM memories
                WHERE access_count >= $1
                AND status = 'active'
                ORDER BY access_count DESC
                LIMIT $2
                """,
                min_access_count,
                limit,
            )
            return [row["id"] for row in rows]

    async def get_stale(self, days: int = 30, limit: int = 100) -> list[UUID]:
        """Get IDs of memories that haven't been accessed recently.

        Args:
            days: Number of days after which a memory is considered stale.
            limit: Maximum number of results.

        Returns:
            List of stale memory IDs.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM memories
                WHERE (last_accessed IS NULL AND updated_at < $1)
                OR (last_accessed IS NOT NULL AND last_accessed < $1)
                AND status = 'active'
                ORDER BY COALESCE(last_accessed, updated_at) ASC
                LIMIT $2
                """,
                cutoff,
                limit,
            )
            return [row["id"] for row in rows]

    async def get_by_status(
        self, status: MemoryStatus, limit: int = 100
    ) -> list[UUID]:
        """Get memory IDs filtered by status.

        Args:
            status: The status to filter by.
            limit: Maximum number of results.

        Returns:
            List of memory IDs with the specified status.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id FROM memories
                WHERE status = $1
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                status.value,
                limit,
            )
            return [row["id"] for row in rows]

    async def count_by_status(self) -> dict[str, int]:
        """Get counts of memories grouped by status.

        Returns:
            Dictionary mapping status strings to counts.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT status, COUNT(*) as count FROM memories GROUP BY status"
            )
            return {row["status"]: row["count"] for row in rows}

    async def update_importance(
        self, memory_id: UUID, importance: float
    ) -> None:
        """Update the importance score for a memory.

        Args:
            memory_id: The memory ID to update.
            importance: New importance score (0.0 to 1.0).
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memories SET importance = $2, updated_at = NOW()
                WHERE id = $1
                """,
                memory_id,
                importance,
            )

    async def increment_access(self, memory_id: UUID) -> None:
        """Increment the access count for a memory.

        Args:
            memory_id: The memory ID to update.
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memories
                SET access_count = access_count + 1,
                    last_accessed = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                memory_id,
            )
