"""PostgreSQL 記憶元數據管理。

此模組處理元數據索引和查詢，
提供按重要性、新近度和訪問模式的高效過濾。
"""

import asyncpg
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from ..models import MemoryNode, MemoryStoreConfig, MemoryStatus


class MemoryIndex:
    """Memory 對象的元數據索引和過濾。

    提供超越內容本身的高效元數據字段查詢。
    """

    def __init__(self, config: MemoryStoreConfig):
        """使用數據庫配置初始化記憶索引。

        Args:
            config: 數據庫連接配置。
        """
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """建立與 PostgreSQL 的連接池。"""
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
        """關閉連接池。"""
        if self._pool:
            await self._pool.close()

    async def init_schema(self) -> None:
        """使用額外索引初始化元數據索引結構。"""
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
        """獲取按最低重要性過濾的記憶 ID。

        Args:
            min_importance: 最低重要性閾值（0.0 到 1.0）。
            limit: 最大結果數。

        Returns:
            滿足閾值的記憶 ID 列表。
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
        """獲取最近更新的記憶 ID。

        Args:
            hours: 回溯的小時數。
            limit: 最大結果數。

        Returns:
            最近記憶 ID 列表。
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
        """獲取頻繁訪問的記憶 ID。

        Args:
            min_access_count: 最低訪問次數閾值。
            limit: 最大結果數。

        Returns:
            頻繁訪問的記憶 ID 列表。
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
        """獲取長時間未訪問的記憶 ID。

        Args:
            days: 記憶被視為過時後的天數。
            limit: 最大結果數。

        Returns:
            過時記憶 ID 列表。
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
        """獲取按狀態過濾的記憶 ID。

        Args:
            status: 要過濾的狀態。
            limit: 最大結果數。

        Returns:
            具有指定狀態的記憶 ID 列表。
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
        """獲取按狀態分組的記憶計數。

        Returns:
            映射狀態字符串到計數的字典。
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT status, COUNT(*) as count FROM memories GROUP BY status"
            )
            return {row["status"]: row["count"] for row in rows}

    async def update_importance(
        self, memory_id: UUID, importance: float
    ) -> None:
        """更新記憶的重要性分數。

        Args:
            memory_id: 要更新的記憶 ID。
            importance: 新的重要性分數（0.0 到 1.0）。
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
        """增加記憶的訪問次數。

        Args:
            memory_id: 要更新的記憶 ID。
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
