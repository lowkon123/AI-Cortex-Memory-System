"""Timeline Snapshot — 系統狀態快照與時間線管理。

修復問題 #38：系統缺乏「當前狀態」的明確時間線快照，
AI 難以理解「現在的真相是什麼」。

此模組定期（或按需）生成「系統認知快照」，記錄當前：
- 最高重要性記憶摘要
- 活躍概念標籤分佈
- 最近發生的重要事件
讓 AI 在對話開始時就能快速定位「我現在的認知狀態」。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from ..models import MemoryKind, MemoryNode, MemorySource, MemoryStatus, utc_now


class TimelineSnapshot:
    """生成與管理系統的認知狀態快照。

    一個快照 = 一個特殊的 MemoryNode（kind=FACT, source=SYSTEM），
    其 content 是對當前系統認知狀態的文字摘要，
    metadata 包含結構化的統計數據。
    """

    SNAPSHOT_TAG = "__timeline_snapshot__"

    def __init__(
        self,
        persona: str = "default",
        snapshot_interval_hours: int = 24,
    ):
        """初始化 TimelineSnapshot。

        Args:
            persona: 要生成快照的人格命名空間。
            snapshot_interval_hours: 自動快照的間隔（小時）。
        """
        self.persona = persona
        self.snapshot_interval_hours = snapshot_interval_hours
        self._last_snapshot_at: Optional[datetime] = None

    async def capture(self, store) -> MemoryNode:
        """生成當前系統的認知狀態快照並存入記憶庫。

        Args:
            store: MemoryStore 實例。

        Returns:
            已存入的快照 MemoryNode。
        """
        # 獲取所有活躍記憶
        all_memories = await store.list_by_persona(self.persona, limit=500)
        active = [m for m in all_memories if m.status == MemoryStatus.ACTIVE]

        # 計算統計數據
        stats = self._compute_stats(active)

        # 生成快照摘要文字
        summary = self._format_summary(stats)

        # 建立快照節點
        snapshot_node = MemoryNode(
            content=summary,
            summary_l1=f"系統快照 @ {utc_now().strftime('%Y-%m-%d %H:%M UTC')}",
            summary_l0="認知狀態快照",
            importance=0.8,
            memory_kind=MemoryKind.FACT,
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
        """從記憶列表中計算結構化統計數據。"""
        if not memories:
            return {"total": 0}

        # 按 kind 分類計數
        kind_counts: dict[str, int] = {}
        for m in memories:
            kind_counts[m.memory_kind.value] = kind_counts.get(m.memory_kind.value, 0) + 1

        # 前 5 高重要性記憶
        top_important = sorted(memories, key=lambda m: m.importance + m.importance_boost, reverse=True)[:5]

        # 前 10 活躍概念標籤
        tag_freq: dict[str, int] = {}
        for m in memories:
            for tag in m.concept_tags:
                tag_freq[tag] = tag_freq.get(tag, 0) + 1
        top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        # 最近 5 條記憶
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
        """將統計數據格式化為人類可讀的快照摘要。"""
        if not stats.get("total"):
            return "系統認知快照：目前記憶庫為空。"

        lines = [
            f"【系統認知快照】@ {utc_now().strftime('%Y年%m月%d日 %H:%M UTC')}",
            f"記憶總量：{stats['total']} 條",
            f"平均重要性：{stats.get('avg_importance', 0):.2f}  |  平均信心值：{stats.get('avg_confidence', 0):.2f}",
            "",
        ]

        # 分類分佈
        kind_dist = stats.get("kind_distribution", {})
        if kind_dist:
            dist_str = " | ".join(f"{k}: {v}" for k, v in kind_dist.items())
            lines.append(f"記憶類型分佈：{dist_str}")

        # 頂部概念
        top_tags = stats.get("top_concept_tags", [])
        if top_tags:
            lines.append(f"核心概念：{', '.join(top_tags[:8])}")

        # 高重要性記憶
        top_summaries = stats.get("top_important_summaries", [])
        if top_summaries:
            lines.append("")
            lines.append("最重要的知識：")
            for i, s in enumerate(top_summaries, 1):
                lines.append(f"  {i}. {s}")

        # 最近活動
        recent = stats.get("recent_memories", [])
        if recent:
            lines.append("")
            lines.append("最近記憶：")
            for s in recent[:3]:
                lines.append(f"  • {s}")

        return "\n".join(lines)

    def should_capture(self) -> bool:
        """判斷是否到了自動快照的時間。"""
        if self._last_snapshot_at is None:
            return True
        from datetime import timedelta
        elapsed = utc_now() - self._last_snapshot_at
        return elapsed.total_seconds() >= self.snapshot_interval_hours * 3600

    async def get_latest_snapshot(self, store) -> Optional[MemoryNode]:
        """從記憶庫中取得最新的快照節點。

        Args:
            store: MemoryStore 實例。

        Returns:
            最新的快照 MemoryNode，若不存在則為 None。
        """
        memories = await store.list_by_concepts(
            [self.SNAPSHOT_TAG], limit=1
        )
        return memories[0] if memories else None

    async def auto_capture(self, store) -> Optional[MemoryNode]:
        """若應生成快照則自動生成，否則返回 None。"""
        if self.should_capture():
            return await self.capture(store)
        return None

    async def get_snapshot_history(self, store, limit: int = 10) -> list[MemoryNode]:
        """取得歷史快照列表。

        Args:
            store: MemoryStore 實例。
            limit: 最多返回幾個快照。

        Returns:
            快照 MemoryNode 列表（按時間降序）。
        """
        memories = await store.list_by_concepts([self.SNAPSHOT_TAG], limit=limit)
        return sorted(memories, key=lambda m: m.created_at, reverse=True)
