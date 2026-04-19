"""Bias Detector — 記憶偏見審計系統。

修復問題 #48：AI 的決策可能被歷史記憶汙染，形成「認知偏見」。

例如：若大多數關於某技術的記憶都是負面的（因為早期踩坑），
AI 可能會持續對該技術產生偏見，即使情況已改變。

此模組提供：
1. 偏見分佈分析（情感偏向、重要性偏向）
2. 記憶多樣性評分（避免 Echo Chamber 效應）
3. 衝突記憶識別（找出矛盾的決策依據）
4. 偏見警示標記（在高偏見場景下告知 AI）
"""

from __future__ import annotations

from collections import Counter
from typing import Optional
from uuid import UUID

from ..models import MemoryKind, MemoryNode, MemoryStatus


class BiasReport:
    """記憶偏見審計結果。"""

    def __init__(
        self,
        total_analyzed: int,
        sentiment_distribution: dict[str, float],
        diversity_score: float,
        conflict_pairs: list[tuple[UUID, UUID]],
        dominant_concepts: list[str],
        bias_warnings: list[str],
    ):
        self.total_analyzed = total_analyzed
        self.sentiment_distribution = sentiment_distribution
        self.diversity_score = diversity_score
        self.conflict_pairs = conflict_pairs
        self.dominant_concepts = dominant_concepts
        self.bias_warnings = bias_warnings

    @property
    def is_biased(self) -> bool:
        """判斷記憶庫是否存在明顯偏見。"""
        return len(self.bias_warnings) > 0

    @property
    def bias_level(self) -> str:
        """偏見程度評級。"""
        n = len(self.bias_warnings)
        if n == 0:
            return "healthy"
        if n <= 1:
            return "mild"
        if n <= 3:
            return "moderate"
        return "severe"

    def summary(self) -> str:
        """生成偏見審計摘要文字（可注入 System Prompt）。"""
        if not self.is_biased:
            return "【記憶健康度】良好：記憶庫無明顯認知偏見。"

        lines = [f"【認知偏見警示】等級：{self.bias_level.upper()}"]
        for w in self.bias_warnings:
            lines.append(f"  ⚠️ {w}")
        lines.append(f"多樣性評分：{self.diversity_score:.2f} / 1.0（越高越均衡）")
        return "\n".join(lines)


class BiasDetector:
    """分析記憶庫是否存在系統性認知偏見。

    偏見類型：
    - 情感偏見：記憶中對某主題的情感傾向過度集中（全正/全負）
    - 概念偏見：少數概念佔據了絕大多數記憶資源（Echo Chamber）
    - 衝突偏見：存在直接矛盾的高重要性記憶（決策不穩定）
    - 新舊偏見：舊記憶的重要性過高，可能遮蔽新的認知（Anchoring Bias）
    """

    def __init__(
        self,
        sentiment_skew_threshold: float = 0.75,
        concept_dominance_threshold: float = 0.50,
        diversity_min_threshold: float = 0.30,
    ):
        """初始化 BiasDetector。

        Args:
            sentiment_skew_threshold: 情感偏向超過此比例視為偏見（0–1）。
            concept_dominance_threshold: 單一概念佔所有記憶超過此比例視為 Echo Chamber。
            diversity_min_threshold: 記憶多樣性評分低於此值發出警示。
        """
        self.sentiment_skew_threshold = sentiment_skew_threshold
        self.concept_dominance_threshold = concept_dominance_threshold
        self.diversity_min_threshold = diversity_min_threshold

    def analyze(
        self,
        memories: list[MemoryNode],
        topic: Optional[str] = None,
    ) -> BiasReport:
        """對記憶列表進行偏見審計。

        Args:
            memories: 要分析的記憶節點列表。
            topic: 可選的主題過濾（只分析包含此詞的記憶）。

        Returns:
            BiasReport 物件。
        """
        if topic:
            memories = [m for m in memories if topic in m.content or topic in " ".join(m.concept_tags)]

        active = [m for m in memories if m.status == MemoryStatus.ACTIVE]
        if not active:
            return BiasReport(
                total_analyzed=0,
                sentiment_distribution={},
                diversity_score=1.0,
                conflict_pairs=[],
                dominant_concepts=[],
                bias_warnings=[],
            )

        warnings: list[str] = []

        # 1. 情感分佈分析
        sentiment_dist = self._analyze_sentiment(active)
        dominant_sentiment = max(sentiment_dist, key=sentiment_dist.get, default=None)
        if dominant_sentiment and sentiment_dist.get(dominant_sentiment, 0) > self.sentiment_skew_threshold:
            warnings.append(
                f"情感偏見：{dominant_sentiment} 情感佔比 {sentiment_dist[dominant_sentiment]:.0%}，"
                f"可能導致評估時情感失衡"
            )

        # 2. 概念多樣性分析
        diversity_score = self._compute_diversity(active)
        if diversity_score < self.diversity_min_threshold:
            warnings.append(
                f"記憶單一化：多樣性評分 {diversity_score:.2f}，"
                f"記憶庫可能存在 Echo Chamber 效應"
            )

        # 3. 主導概念分析
        dominant_concepts = self._find_dominant_concepts(active)
        if dominant_concepts:
            top_concept, top_ratio = dominant_concepts[0]
            if top_ratio > self.concept_dominance_threshold:
                warnings.append(
                    f"概念支配：「{top_concept}」佔所有記憶的 {top_ratio:.0%}，"
                    f"AI 決策可能被此概念過度主導"
                )

        # 4. 衝突記憶識別
        conflict_pairs = self._find_conflict_pairs(active)
        if len(conflict_pairs) > 3:
            warnings.append(
                f"決策衝突：發現 {len(conflict_pairs)} 對矛盾記憶，"
                f"AI 在相關主題上的判斷可能不穩定"
            )

        # 5. 新舊偏見（Anchoring Bias）
        anchoring_issue = self._check_anchoring_bias(active)
        if anchoring_issue:
            warnings.append(anchoring_issue)

        return BiasReport(
            total_analyzed=len(active),
            sentiment_distribution=sentiment_dist,
            diversity_score=diversity_score,
            conflict_pairs=conflict_pairs,
            dominant_concepts=[c for c, _ in dominant_concepts[:5]],
            bias_warnings=warnings,
        )

    def _analyze_sentiment(self, memories: list[MemoryNode]) -> dict[str, float]:
        """計算各情感類型的比例分佈。"""
        counts: Counter = Counter()
        for m in memories:
            sentiment = m.sentiment or "neutral"
            counts[sentiment] += 1
        total = len(memories) or 1
        return {k: round(v / total, 3) for k, v in counts.items()}

    def _compute_diversity(self, memories: list[MemoryNode]) -> float:
        """計算記憶庫的概念多樣性（Shannon Entropy 正規化）。

        0.0 = 完全單一化，1.0 = 完全均衡分佈。
        """
        import math

        all_tags: list[str] = []
        for m in memories:
            all_tags.extend(m.concept_tags[:3])

        if not all_tags:
            return 0.5  # 無標籤，給中性分數

        freq = Counter(all_tags)
        total = sum(freq.values())
        entropy = -sum((c / total) * math.log2(c / total) for c in freq.values())

        # 最大熵（均勻分佈）
        max_entropy = math.log2(len(freq)) if len(freq) > 1 else 1.0
        return round(entropy / max_entropy, 3) if max_entropy > 0 else 0.0

    def _find_dominant_concepts(
        self, memories: list[MemoryNode]
    ) -> list[tuple[str, float]]:
        """找出支配性概念標籤及其佔比。"""
        all_tags: list[str] = []
        for m in memories:
            all_tags.extend(m.concept_tags)

        if not all_tags:
            return []

        freq = Counter(all_tags)
        total = len(all_tags)
        return [
            (tag, round(count / total, 3))
            for tag, count in freq.most_common(10)
        ]

    def _find_conflict_pairs(
        self, memories: list[MemoryNode]
    ) -> list[tuple[UUID, UUID]]:
        """找出已標記的衝突記憶對。"""
        pairs: list[tuple[UUID, UUID]] = []
        for m in memories:
            if m.conflict_with:
                pair = tuple(sorted([str(m.id), str(m.conflict_with)]))
                if pair not in [tuple(sorted([str(a), str(b)])) for a, b in pairs]:
                    pairs.append((m.id, m.conflict_with))
        return pairs

    def _check_anchoring_bias(self, memories: list[MemoryNode]) -> Optional[str]:
        """檢查舊記憶是否佔據過高的重要性（Anchoring Bias）。"""
        from datetime import timedelta
        from ..models import utc_now

        now = utc_now()
        old_threshold = now - timedelta(days=90)

        old_high_importance = [
            m for m in memories
            if m.created_at < old_threshold
            and (m.importance + m.importance_boost) > 0.8
        ]
        ratio = len(old_high_importance) / len(memories) if memories else 0

        if ratio > 0.4:
            return (
                f"錨定偏見：{ratio:.0%} 的高重要性記憶超過 90 天未更新，"
                f"可能阻礙 AI 接受新資訊"
            )
        return None

    def get_bias_injection(self, memories: list[MemoryNode], topic: Optional[str] = None) -> str:
        """生成適合注入 System Prompt 的偏見警示文字。

        Args:
            memories: 要分析的記憶列表。
            topic: 可選主題過濾。

        Returns:
            若有偏見則回傳警示文字，否則回傳空字串。
        """
        report = self.analyze(memories, topic=topic)
        if not report.is_biased:
            return ""
        return "\n" + report.summary() + "\n"
