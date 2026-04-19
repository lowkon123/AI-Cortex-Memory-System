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
    async def hybrid_search(
        self, query: str, query_vector: list[float], limit: int = 20
    ) -> list[UUID]:
        """執行混合搜尋 (關鍵字過濾 + 向量相似度)。

        Args:
            query: 搜尋關鍵字。
            query_vector: 查詢向量。
            limit: 結果數量上限。

        Returns:
            相關記憶 ID 列表。
        """
        async with self._pool.acquire() as conn:
            # 結合 FTS (Full Text Search) 與向量餘弦相似度
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
        """建立高效能 HNSW 向量索引（替換預設的 ivfflat）。

        修復問題 #42：大型記憶庫下向量搜尋延遲上升。
        HNSW (Hierarchical Navigable Small World) 在百萬級向量下
        比 ivfflat 的查詢速度快 3–10 倍。

        注意：此操作使用 CONCURRENTLY，不阻塞線上查詢。
        """
        async with self._pool.acquire() as conn:
            # 先刪除舊索引再建新索引（若存在）
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
        """多意圖查詢：對多個子查詢分別搜尋後合併去重。

        修復問題 #14：單一複合問題（如「告訴我用戶的習慣和專案狀況」）
        過去只搜尋單一向量，現在支援將複合問題拆分為多個子查詢並合併。

        Args:
            queries: 子查詢字串列表（用於 FTS）。
            query_vectors: 對應的子查詢向量列表。
            limit: 最終合併後的最大結果數。

        Returns:
            合併去重後的記憶 UUID 列表。
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
        """帶降級保護的混合搜尋。

        修復問題 #44：Retrieval Pipeline 不穩時回應波動。
        若向量搜尋失敗（DB 超時/索引損壞），自動降級到純 FTS 搜尋。

        Args:
            query: 搜尋關鍵字。
            query_vector: 查詢向量。
            limit: 結果數量上限。
            fallback_fts_only: 若 True，向量搜尋失敗時退回純 FTS。

        Returns:
            記憶 UUID 列表。
        """
        try:
            return await self.hybrid_search(query, query_vector, limit)
        except Exception:
            if not fallback_fts_only:
                return []
            # Fallback: 純 FTS 搜尋
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
        """擴展檢索：尋找與指定節點有連結的鄰居節點。"""
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
