"""Epistemic Marker — 認識論標記系統。

修復問題 #8：明確區分記憶中的「事實/推測/觀點/假設」，
防止 AI 將推測性結論當作確鑿事實來引用。

每條記憶現在擁有一個 `epistemic_type`，影響：
- 排名權重（已確認事實 > 推測 > 假設）
- 衝突偵測敏感度（事實矛盾 > 觀點矛盾）
- Confidence 分數計算邊界
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from ..models import MemoryNode


class EpistemicType(str, Enum):
    """記憶的認識論類型。"""

    FACT = "fact"
    """已驗證的客觀事實。例：「Python 是直譯語言」"""

    INFERENCE = "inference"
    """基於現有事實的邏輯推論。例：「根據程式碼，用戶偏好函數式風格」"""

    BELIEF = "belief"
    """使用者的主觀看法或偏好。例：「用戶認為 TypeScript 比 JavaScript 好」"""

    HYPOTHESIS = "hypothesis"
    """尚未驗證的假設。例：「可能是記憶體洩漏導致崩潰」"""

    SPECULATION = "speculation"
    """純粹的推測，幾乎無事實基礎。例：「也許用戶想換框架？」"""


# 每種認識論類型的 Confidence 上限（防止推測被高度信任）
EPISTEMIC_CONFIDENCE_CAPS: dict[EpistemicType, float] = {
    EpistemicType.FACT: 1.0,
    EpistemicType.INFERENCE: 0.85,
    EpistemicType.BELIEF: 0.75,
    EpistemicType.HYPOTHESIS: 0.60,
    EpistemicType.SPECULATION: 0.40,
}

# 每種認識論類型的排名權重乘數
EPISTEMIC_RANK_MULTIPLIERS: dict[EpistemicType, float] = {
    EpistemicType.FACT: 1.0,
    EpistemicType.INFERENCE: 0.90,
    EpistemicType.BELIEF: 0.80,
    EpistemicType.HYPOTHESIS: 0.65,
    EpistemicType.SPECULATION: 0.45,
}


class EpistemicMarker:
    """為記憶節點標記和管理認識論類型。"""

    METADATA_KEY = "_epistemic_type"

    def mark(
        self,
        node: MemoryNode,
        epistemic_type: EpistemicType,
        evidence: Optional[str] = None,
    ) -> MemoryNode:
        """為記憶節點標記認識論類型。

        Args:
            node: 要標記的記憶節點。
            epistemic_type: 認識論類型。
            evidence: 可選的佐證說明（例如哪條記憶支撐了這個推論）。

        Returns:
            已標記的記憶節點（就地修改）。
        """
        node.metadata[self.METADATA_KEY] = epistemic_type.value

        # 套用 Confidence 上限
        cap = EPISTEMIC_CONFIDENCE_CAPS[epistemic_type]
        node.confidence = min(node.confidence, cap)

        if evidence:
            node.metadata["_epistemic_evidence"] = evidence

        return node

    def get_type(self, node: MemoryNode) -> EpistemicType:
        """從記憶節點讀取認識論類型。預設為 INFERENCE（保守假設）。"""
        raw = node.metadata.get(self.METADATA_KEY, EpistemicType.INFERENCE.value)
        try:
            return EpistemicType(raw)
        except ValueError:
            return EpistemicType.INFERENCE

    def get_rank_multiplier(self, node: MemoryNode) -> float:
        """取得此節點應用於排名的信心乘數。"""
        etype = self.get_type(node)
        return EPISTEMIC_RANK_MULTIPLIERS.get(etype, 0.75)

    def apply_to_score(self, node: MemoryNode, base_score: float) -> float:
        """將認識論乘數應用到基礎排名分數。"""
        return base_score * self.get_rank_multiplier(node)

    def is_reliable(self, node: MemoryNode, min_confidence: float = 0.65) -> bool:
        """判斷記憶是否足夠可靠（適合作為決策依據）。"""
        etype = self.get_type(node)
        if etype in (EpistemicType.SPECULATION, EpistemicType.HYPOTHESIS):
            return False
        return node.confidence >= min_confidence

    def infer_from_source(self, node: MemoryNode) -> EpistemicType:
        """根據記憶的來源類型自動推斷認識論類型（啟發式規則）。"""
        from ..models import MemoryKind, MemorySource

        if node.source_type == MemorySource.INFERRED:
            return EpistemicType.INFERENCE
        if node.memory_kind == MemoryKind.FACT:
            return EpistemicType.FACT
        if node.memory_kind == MemoryKind.CONCEPT:
            return EpistemicType.INFERENCE
        if node.memory_kind in (MemoryKind.EPISODIC, MemoryKind.WORKING):
            return EpistemicType.BELIEF
        return EpistemicType.INFERENCE

    def auto_mark(self, node: MemoryNode) -> MemoryNode:
        """根據 MemorySource 和 MemoryKind 自動賦予認識論標記。"""
        inferred_type = self.infer_from_source(node)
        return self.mark(node, inferred_type)

    def filter_reliable(
        self, nodes: list[MemoryNode], min_confidence: float = 0.65
    ) -> list[MemoryNode]:
        """從列表中過濾出可靠的記憶（排除低信度推測）。"""
        return [n for n in nodes if self.is_reliable(n, min_confidence)]

    def summarize(self, nodes: list[MemoryNode]) -> dict[str, int]:
        """統計列表中各認識論類型的分佈。"""
        counts: dict[str, int] = {t.value: 0 for t in EpistemicType}
        for node in nodes:
            etype = self.get_type(node)
            counts[etype.value] += 1
        return counts
