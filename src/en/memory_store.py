"""PostgreSQL persistence layer for memory objects.

This module handles the raw storage of Memory objects in PostgreSQL,
providing async insert/update/delete operations with connection pooling.
"""

import asyncpg
from typing import Optional
from uuid import UUID

from ..models import MemoryNode, MemoryStoreConfig


class MemoryStore:
    """Persistence layer for MemoryNode objects using PostgreSQL.

    Provides async CRUD operations with connection pooling.
    """

    def __init__(self, config: MemoryStoreConfig):
        """Initialize the memory store with database configuration.

        Args:
            config: Database connection configuration.
        """
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        async def setup(conn):
            # Register pgvector codec
            await conn.set_type_codec(
                "vector",
                encoder=lambda v: str(v),
                decoder=lambda v: [float(x) for x in v[1:-1].split(",")],
                schema="public",
                format="text",
            )

        self._pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            min_size=2,
            max_size=self.config.pool_size,
            setup=setup,
        )

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()

    async def init_schema(self) -> None:
        """Initialize the memory table schema."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS memories (
                    id UUID PRIMARY KEY,
                    content TEXT NOT NULL,
                    summary_l1 TEXT,
                    summary_l0 TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    importance FLOAT NOT NULL DEFAULT 0.5,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed TIMESTAMPTZ,
                    importance_boost FLOAT NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'active',
                    embedding vector({self.config.vector_dim}),
                    zoom_level TEXT NOT NULL DEFAULT 'l2'
                )
            """)

    async def insert(self, memory: MemoryNode) -> MemoryNode:
        """Insert a new memory into the store.

        Args:
            memory: The memory node to persist.

        Returns:
            The persisted memory node with confirmed ID.
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (
                    id, content, summary_l1, summary_l0, created_at, updated_at,
                    importance, access_count, last_accessed, importance_boost,
                    status, embedding, zoom_level
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                memory.id,
                memory.content,
                memory.summary_l1,
                memory.summary_l0,
                memory.created_at,
                memory.updated_at,
                memory.importance,
                memory.access_count,
                memory.last_accessed,
                memory.importance_boost,
                memory.status.value,
                memory.embedding,
                memory.zoom_level.value,
            )
        return memory

    async def get(self, memory_id: UUID) -> Optional[MemoryNode]:
        """Retrieve a memory by its ID.

        Args:
            memory_id: The unique identifier of the memory.

        Returns:
            The memory node if found, None otherwise.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM memories WHERE id = $1", memory_id
            )
            if not row:
                return None
            return self._row_to_memory(row)

    async def update(self, memory: MemoryNode) -> MemoryNode:
        """Update an existing memory in the store.

        Args:
            memory: The memory node with updated fields.

        Returns:
            The updated memory node.
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memories SET
                    content = $2,
                    summary_l1 = $3,
                    summary_l0 = $4,
                    updated_at = $5,
                    importance = $6,
                    access_count = $7,
                    last_accessed = $8,
                    importance_boost = $9,
                    status = $10,
                    embedding = $11,
                    zoom_level = $12
                WHERE id = $1
                """,
                memory.id,
                memory.content,
                memory.summary_l1,
                memory.summary_l0,
                memory.updated_at,
                memory.importance,
                memory.access_count,
                memory.last_accessed,
                memory.importance_boost,
                memory.status.value,
                memory.embedding,
                memory.zoom_level.value,
            )
        return memory

    async def delete(self, memory_id: UUID) -> bool:
        """Delete a memory by its ID.

        Args:
            memory_id: The unique identifier of the memory.

        Returns:
            True if the memory was deleted, False if not found.
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memories WHERE id = $1", memory_id
            )
            return "DELETE 1" in result

    async def list_all(self, status: Optional[str] = None, limit: int = 100) -> list[MemoryNode]:
        """List all memories, optionally filtered by status.

        Args:
            status: Optional status filter.
            limit: Maximum number of results.

        Returns:
            List of memory nodes.
        """
        async with self._pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM memories WHERE status = $1 ORDER BY updated_at DESC LIMIT $2",
                    status, limit
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM memories ORDER BY updated_at DESC LIMIT $1", limit
                )
            return [self._row_to_memory(row) for row in rows]

    def _row_to_memory(self, row: asyncpg.Record) -> MemoryNode:
        """Convert a database row to a MemoryNode.

        Args:
            row: The database record.

        Returns:
            A MemoryNode instance.
        """
        from ..models import MemoryStatus, ZoomLevel
        return MemoryNode(
            id=row["id"],
            content=row["content"],
            summary_l1=row["summary_l1"],
            summary_l0=row["summary_l0"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            importance=row["importance"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            importance_boost=row["importance_boost"],
            status=MemoryStatus(row["status"]),
            embedding=row["embedding"],
            zoom_level=ZoomLevel(row["zoom_level"]),
        )
