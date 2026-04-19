"""Index Maintenance — 記憶索引長期健康維護。

修復問題 #20：記憶庫越大，Retrieval 品質越差。

隨著記憶庫增長，向量索引碎片化、統計過時、
查詢計畫不準確等問題會逐漸累積，導致搜尋越來越慢、
召回品質越來越差。

此模組提供定期的「索引健康維護」功能：
- PostgreSQL VACUUM / ANALYZE（更新查詢計畫器統計）
- 向量索引重建（解決碎片化）
- 孤兒節點清理（清除無 Embedding 的廢棄節點）
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from ..models import MemoryStatus, utc_now


class IndexMaintenance:
    """維護記憶庫索引的長期健康狀態。

    修復問題 #20：長期 Retrieval 品質下降。

    定期排程建議：
    - ANALYZE: 每 6 小時（輕量，追蹤 Sleep Cycle）
    - VACUUM: 每 24 小時（中量，系統低負載時）
    - 索引重建: 每 7 天（重量，僅在記憶庫超過 10k 節點時）
    - 孤兒清理: 每 24 小時
    """

    def __init__(
        self,
        analyze_interval_hours: int = 6,
        vacuum_interval_hours: int = 24,
        reindex_interval_days: int = 7,
        orphan_cleanup_interval_hours: int = 24,
    ):
        self.analyze_interval_hours = analyze_interval_hours
        self.vacuum_interval_hours = vacuum_interval_hours
        self.reindex_interval_days = reindex_interval_days
        self.orphan_cleanup_interval_hours = orphan_cleanup_interval_hours

        self._last_analyze: Optional[object] = None
        self._last_vacuum: Optional[object] = None
        self._last_reindex: Optional[object] = None
        self._last_orphan_cleanup: Optional[object] = None

    async def run_analyze(self, pool) -> dict:
        """執行 ANALYZE：更新查詢計畫器的統計數據。

        這是最輕量的維護操作，應頻繁執行。
        確保 PostgreSQL 的查詢優化器使用最新的數據分佈統計。
        """
        async with pool.acquire() as conn:
            await conn.execute("ANALYZE memories")
            await conn.execute("ANALYZE memory_relations")
        self._last_analyze = utc_now()
        return {"operation": "analyze", "status": "ok", "ran_at": self._last_analyze.isoformat()}

    async def run_vacuum(self, pool) -> dict:
        """執行 VACUUM：回收已刪除記憶的磁碟空間。

        Sleep Cycle 軟刪除（FORGOTTEN）的記憶實際上仍佔用空間，
        VACUUM 清理這些死元組，防止表格膨脹。
        """
        async with pool.acquire() as conn:
            # 不可在事務中執行，需要直接連接
            await conn.execute("VACUUM memories")
        self._last_vacuum = utc_now()
        return {"operation": "vacuum", "status": "ok", "ran_at": self._last_vacuum.isoformat()}

    async def run_reindex(self, pool) -> dict:
        """重建向量索引：解決碎片化問題。

        大量插入/刪除後，pgvector HNSW 索引可能碎片化，
        重建索引恢復最佳搜尋效能。
        使用 CONCURRENTLY 不阻塞線上查詢。
        """
        async with pool.acquire() as conn:
            # 重建向量索引（若存在）
            await conn.execute(
                "REINDEX INDEX CONCURRENTLY IF EXISTS idx_memories_embedding_hnsw"
            )
            # 重建 FTS 索引
            await conn.execute(
                "REINDEX INDEX CONCURRENTLY IF EXISTS idx_memories_content_fts"
            )
        self._last_reindex = utc_now()
        return {"operation": "reindex", "status": "ok", "ran_at": self._last_reindex.isoformat()}

    async def cleanup_orphans(self, pool) -> dict:
        """清理孤兒節點：刪除無 Embedding 的遺忘狀態記憶。

        長期 FORGOTTEN 且沒有 Embedding 的節點純屬廢棄數據，
        清理它們能提升索引效率和查詢速度。
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
        """生成索引健康報告。

        Returns:
            包含表格大小、索引狀態、死元組比例等的健康狀況字典。
        """
        async with pool.acquire() as conn:
            # 表格大小
            size_row = await conn.fetchrow(
                "SELECT pg_size_pretty(pg_total_relation_size('memories')) as size"
            )

            # 記憶數量按狀態
            status_rows = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM memories GROUP BY status"
            )

            # 死元組比例
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

            # 索引大小
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
        """判斷是否到了執行維護的時間。"""
        if last_run is None:
            return True
        elapsed = utc_now() - last_run
        return elapsed >= timedelta(hours=interval_hours)

    async def run_scheduled_maintenance(self, pool, total_memories: int = 0) -> list[dict]:
        """根據排程自動執行需要的維護任務。

        Args:
            pool: asyncpg 連接池。
            total_memories: 當前記憶總數（決定是否需要重建索引）。

        Returns:
            已執行的維護任務列表。
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

        # 索引重建只在大型記憶庫且到達排程時執行
        if (
            total_memories > 5000
            and self._is_due(self._last_reindex, self.reindex_interval_days * 24)
        ):
            result = await self.run_reindex(pool)
            completed_tasks.append(result)

        return completed_tasks
