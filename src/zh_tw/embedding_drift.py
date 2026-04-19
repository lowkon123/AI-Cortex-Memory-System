"""Embedding Drift Detector — 語意漂移偵測與自動重算。

修復問題 #19：隨著 Embedding 模型更新，舊記憶的向量可能出現
語意漂移（Semantic Drift），導致相似度計算失準。

此模組定期抽樣舊記憶，計算新舊向量的 cosine 偏移量，
一旦超過漂移門檻就觸發批次重算流程。
"""

from __future__ import annotations

import asyncio
import math
import random
from datetime import UTC, datetime, timedelta
from typing import Optional

import numpy as np

from ..models import MemoryNode, utc_now


class EmbeddingDriftDetector:
    """偵測並修復記憶庫中的 Embedding 語意漂移。

    工作流程：
    1. 抽樣 N 條舊記憶
    2. 用當前 Embedding Provider 重新計算向量
    3. 比較新舊向量的 cosine 距離（Drift Score）
    4. 若平均 Drift > threshold，觸發全量重算
    """

    def __init__(
        self,
        drift_threshold: float = 0.05,
        sample_size: int = 100,
        re_embed_batch_size: int = 50,
        check_interval_days: int = 7,
    ):
        """初始化漂移偵測器。

        Args:
            drift_threshold: 觸發重算的平均漂移門檻（0.0–1.0）。
                0.05 = 5% 偏移即觸發，保守設定。
            sample_size: 每次偵測抽取的記憶數量。
            re_embed_batch_size: 批次重算時每批的大小。
            check_interval_days: 定期檢測的間隔天數。
        """
        self.drift_threshold = drift_threshold
        self.sample_size = sample_size
        self.re_embed_batch_size = re_embed_batch_size
        self.check_interval_days = check_interval_days
        self._last_check: Optional[datetime] = None
        self._last_drift_score: float = 0.0
        self._total_re_embedded: int = 0

    def cosine_distance(self, v1: list[float], v2: list[float]) -> float:
        """計算兩個向量的 cosine 距離（1 - cosine_similarity）。

        距離越大代表漂移越嚴重。0 = 完全相同，2 = 完全相反。
        """
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 1.0
        similarity = float(np.dot(a / norm_a, b / norm_b))
        return 1.0 - max(-1.0, min(1.0, similarity))

    async def detect_drift(
        self,
        store,
        embedding_provider,
        sample_size: Optional[int] = None,
    ) -> dict:
        """偵測記憶庫中的 Embedding 漂移程度。

        Args:
            store: MemoryStore 實例。
            embedding_provider: 當前的 Embedding Provider（需有 get_embedding() 方法）。
            sample_size: 覆蓋預設抽樣數量。

        Returns:
            包含 drift_score, drifted_count, sample_size 等的偵測報告。
        """
        n = sample_size or self.sample_size
        all_memories = await store.list_all(limit=n * 3)

        # 只抽取有 Embedding 的記憶
        candidates = [m for m in all_memories if m.embedding is not None]
        if not candidates:
            return {"drift_score": 0.0, "drifted_count": 0, "sample_size": 0, "needs_re_embed": False}

        sample = random.sample(candidates, min(n, len(candidates)))

        drift_scores: list[float] = []
        drifted_nodes: list[MemoryNode] = []

        for memory in sample:
            try:
                new_embedding = await embedding_provider.get_embedding(memory.content)
                drift = self.cosine_distance(memory.embedding, new_embedding)
                drift_scores.append(drift)
                if drift > self.drift_threshold:
                    drifted_nodes.append(memory)
            except Exception:
                continue

        avg_drift = sum(drift_scores) / len(drift_scores) if drift_scores else 0.0
        self._last_drift_score = avg_drift
        self._last_check = utc_now()

        return {
            "drift_score": round(avg_drift, 4),
            "drifted_count": len(drifted_nodes),
            "sample_size": len(sample),
            "needs_re_embed": avg_drift > self.drift_threshold,
            "drifted_memory_ids": [str(m.id) for m in drifted_nodes],
            "checked_at": self._last_check.isoformat(),
        }

    async def re_embed_all(
        self,
        store,
        embedding_provider,
        dry_run: bool = False,
    ) -> dict:
        """對整個記憶庫執行全量 Re-embedding。

        Args:
            store: MemoryStore 實例。
            embedding_provider: 當前 Embedding Provider。
            dry_run: 若 True，只計算不寫入。

        Returns:
            包含處理數量和更新數量的報告。
        """
        all_memories = await store.list_all(limit=10000)
        candidates = [m for m in all_memories if m.embedding is not None]

        updated = 0
        errors = 0

        # 分批處理，避免記憶體爆炸
        for i in range(0, len(candidates), self.re_embed_batch_size):
            batch = candidates[i: i + self.re_embed_batch_size]
            for memory in batch:
                try:
                    new_embedding = await embedding_provider.get_embedding(memory.content)
                    if not dry_run:
                        memory.embedding = new_embedding
                        memory.updated_at = utc_now()
                        await store.update(memory)
                    updated += 1
                except Exception:
                    errors += 1
            # 每批之間稍作休息，避免 Ollama 過熱
            await asyncio.sleep(0.5)

        self._total_re_embedded += updated

        return {
            "total_candidates": len(candidates),
            "updated": updated,
            "errors": errors,
            "dry_run": dry_run,
        }

    async def re_embed_drifted(
        self,
        store,
        embedding_provider,
        memory_ids: list[str],
    ) -> dict:
        """只對已漂移的記憶重算 Embedding（精準模式）。

        Args:
            store: MemoryStore 實例。
            embedding_provider: 當前 Embedding Provider。
            memory_ids: 需要重算的記憶 UUID 字串列表。

        Returns:
            處理報告。
        """
        from uuid import UUID

        updated = 0
        errors = 0

        for id_str in memory_ids:
            try:
                memory = await store.get(UUID(id_str))
                if not memory:
                    continue
                new_embedding = await embedding_provider.get_embedding(memory.content)
                memory.embedding = new_embedding
                memory.updated_at = utc_now()
                await store.update(memory)
                updated += 1
            except Exception:
                errors += 1

        self._total_re_embedded += updated
        return {"updated": updated, "errors": errors}

    def should_check(self) -> bool:
        """判斷是否到了定期偵測的時間。"""
        if self._last_check is None:
            return True
        elapsed = utc_now() - self._last_check
        return elapsed >= timedelta(days=self.check_interval_days)

    def get_status(self) -> dict:
        """取得偵測器的當前狀態。"""
        return {
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "last_drift_score": self._last_drift_score,
            "drift_threshold": self.drift_threshold,
            "total_re_embedded": self._total_re_embedded,
            "next_check_due": self.should_check(),
        }

    async def run_weekly_maintenance(
        self, store, embedding_provider, auto_fix: bool = True
    ) -> dict:
        """每週自動維護：偵測 → 有漂移即精準重算。

        Args:
            store: MemoryStore 實例。
            embedding_provider: Embedding Provider。
            auto_fix: 若 True，偵測到漂移後自動重算。

        Returns:
            完整的維護報告。
        """
        if not self.should_check():
            return {"skipped": True, "reason": "not_due_yet", **self.get_status()}

        report = await self.detect_drift(store, embedding_provider)

        if report["needs_re_embed"] and auto_fix:
            fix_report = await self.re_embed_drifted(
                store, embedding_provider, report["drifted_memory_ids"]
            )
            report["fix_report"] = fix_report

        return report
