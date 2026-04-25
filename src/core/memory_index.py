"""PostgreSQL metadata indexing and querying for memory nodes.

This module handles metadata indexing and querying, providing efficient 
filtering based on importance, recency, and access patterns.
"""

from __future__ import annotations

import asyncpg
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from ..models import MemoryNode, MemoryStoreConfig, MemoryStatus


class MemoryIndex:
    """Metadata indexing and filtering for Memory nodes.

    Provides efficient querying of metadata fields beyond content itself.
    """

    def __init__(self, config: MemoryStoreConfig):
        """Initialize memory index with database configuration.

        Args:
            config: Database connection configuration.
        """
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish connection pool with PostgreSQL."""
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
        """Initialize metadata indexing structure with additional indices."""
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
        """Fetch memory IDs filtered by minimum importance.

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
        """Fetch IDs of recently updated memories.

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
        """Fetch IDs of frequently accessed memories.

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
        """Fetch IDs of memories not accessed for a long period.

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
        """Fetch memory IDs filtered by status.

        Args:
            status: Status to filter by.
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
        """Update the importance score of a memory.

        Args:
            memory_id: ID of the memory to update.
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
        """Increment the access count of a memory.

        Args:
            memory_id: ID of the memory to update.
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

    async def hybrid_search(
        self, query: str, query_vector: list[float], limit: int = 20
    ) -> list[UUID]:
        """Perform hybrid search (keyword filtering + vector similarity).

        Args:
            query: Search keyword.
            query_vector: Query vector.
            limit: Maximum result limit.

        Returns:
            List of relevant memory IDs.
        """
        async with self._pool.acquire() as conn:
            # Combine FTS with vector cosine similarity
            rows = await conn.fetch(
                f"""
                WITH keyword_matches AS (
                    SELECT id, 0.3 as keyword_score
                    FROM memories
                    WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', $1)
                )
                SELECT m.id, 
                       (1 - (m.embedding <=> $2)) as vector_score,
                       COALESCE(k.keyword_score, 0) as k_score
                FROM memories m
                LEFT JOIN keyword_matches k ON m.id = k.id
                WHERE m.status = 'active'
                ORDER BY (vector_score + k_score) DESC
                LIMIT $3
                """,
                query,
                str(query_vector),
                limit,
            )
            return [row["id"] for row in rows]

    async def create_hnsw_index(self) -> None:
        """Create high-performance HNSW vector index (replaces default ivfflat).

        Fixes #42: Vector search latency rises in large memory stores.
        HNSW (Hierarchical Navigable Small World) is 3-10x faster than 
        ivfflat for queries in datasets with millions of vectors.

        Note: Uses CONCURRENTLY, does not block online queries.
        """
        async with self._pool.acquire() as conn:
            # Drop old index before creating new one (if it exists)
            await conn.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS idx_memories_embedding_hnsw"
            )
            await conn.execute(
                """
                CREATE INDEX CONCURRENTLY idx_memories_embedding_hnsw
                ON memories USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
                """
            )

    async def multi_intent_search(
        self,
        queries: list[str],
        query_vectors: list[list[float]],
        limit: int = 20,
    ) -> list[UUID]:
        """Multi-intent search: Query multiple sub-queries separately then merge.

        Fixes #14: Support for compound questions (e.g., "tell me about user habits and project status").
        Instead of searching with one vector, split or handle multiple intents and merge results.

        Args:
            queries: List of sub-query strings (for FTS).
            query_vectors: List of corresponding sub-query vectors.
            limit: Final maximum result count after merging.

        Returns:
            Merged and deduplicated list of memory UUIDs.
        """
        all_ids: list[UUID] = []
        seen: set[UUID] = set()

        for query, query_vector in zip(queries, query_vectors):
            sub_results = await self.hybrid_search(query, query_vector, limit=limit)
            for uid in sub_results:
                if uid not in seen:
                    seen.add(uid)
                    all_ids.append(uid)

        return all_ids[:limit]

    async def hybrid_search_with_fallback(
        self,
        query: str,
        query_vector: list[float],
        limit: int = 20,
        fallback_fts_only: bool = True,
    ) -> list[UUID]:
        """Hybrid search with graceful degradation fallback.

        Fixes #44: Fluctuating responses when Retrieval Pipeline is unstable.
        Automatically falls back to pure FTS search if vector search fails.

        Args:
            query: Search keyword.
            query_vector: Query vector.
            limit: Result limit.
            fallback_fts_only: If True, falls back to pure FTS on vector failure.

        Returns:
            List of memory UUIDs.
        """
        try:
            return await self.hybrid_search(query, query_vector, limit)
        except Exception:
            if not fallback_fts_only:
                return []
            # Fallback: Pure FTS search
            try:
                async with self._pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id FROM memories
                        WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', $1)
                        AND status = 'active'
                        ORDER BY ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', $1)) DESC
                        LIMIT $2
                        """,
                        query,
                        limit,
                    )
                    return [row["id"] for row in rows]
            except Exception:
                return []

    async def get_neighbor_ids(self, memory_ids: list[UUID], limit: int = 10) -> list[UUID]:
        """Expanded retrieval: Find neighbors linked to specific nodes in Knowledge Graph."""
        if not memory_ids:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT CASE 
                    WHEN source_id = ANY($1) THEN target_id 
                    ELSE source_id 
                END as neighbor_id
                FROM memory_relations
                WHERE source_id = ANY($1) OR target_id = ANY($1)
                LIMIT $2
                """,
                memory_ids,
                limit,
            )
            return [row["neighbor_id"] for row in rows]
