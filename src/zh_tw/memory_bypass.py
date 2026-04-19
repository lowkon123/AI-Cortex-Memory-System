"""Memory Bypass Policy — 推理優先模式。

修復問題 #47：避免 AI 過度依賴記憶查詢，退化成「查字典機器」。

某些 Query 類型天生不需要記憶支援（數學推導、邏輯假設分析）——
強制查詢記憶只會浪費時間，甚至引入錯誤的歷史偏見。

此模組提供：
1. 基於規則的 Bypass 判斷（快速）
2. 可設定的豁免清單（使用者自訂）
3. 混合模式（優先推理，記憶僅作輔助）
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class BypassMode(str, Enum):
    """記憶查詢的 Bypass 模式。"""

    FULL = "full"
    """完全跳過記憶查詢。純推理模式。"""

    SOFT = "soft"
    """降低記憶查詢優先級。記憶作為輔助，推理為主。"""

    NONE = "none"
    """正常模式，完整使用記憶系統。"""


class MemoryBypassPolicy:
    """決定是否需要繞過記憶系統進行純推理的策略層。

    設計哲學：
        記憶系統是 AI 的「長期背景」，但不應是「唯一思維來源」。
        對於數學、邏輯、創意生成等場景，讓 AI 重新推理
        往往比從記憶中「照本宣科」更準確。
    """

    # 預設觸發完全 Bypass 的模式（高信心）
    FULL_BYPASS_PATTERNS: list[str] = [
        r"計算.{0,20}[0-9]",           # 含數字的計算
        r"[0-9]+\s*[\+\-\*\/\^]\s*[0-9]+",  # 數學運算式
        r"推導|證明|解方程",             # 數學推導
        r"假設.{0,10}如果",             # 反事實假設
        r"如果.{0,20}會怎|會發生什麼",   # 假設性思考
        r"用.*演算法.*解",               # 演算法分析
    ]

    # 預設觸發軟 Bypass 的模式（保留部分記憶參考）
    SOFT_BYPASS_PATTERNS: list[str] = [
        r"想像|創意|設計一個",           # 創意生成
        r"幫我寫.*故事|寫一篇",          # 創作類
        r"比較.*優缺點",                 # 分析比較（記憶可作基礎）
        r"解釋.*概念|什麼是",            # 概念解釋（記憶作補充）
        r"邏輯上.*應該",                 # 邏輯推理（輔助記憶）
    ]

    def __init__(
        self,
        full_bypass_patterns: Optional[list[str]] = None,
        soft_bypass_patterns: Optional[list[str]] = None,
        custom_full_terms: Optional[list[str]] = None,
        custom_soft_terms: Optional[list[str]] = None,
        enabled: bool = True,
    ):
        """初始化 Bypass Policy。

        Args:
            full_bypass_patterns: 覆蓋預設的完全 Bypass 正則列表。
            soft_bypass_patterns: 覆蓋預設的軟 Bypass 正則列表。
            custom_full_terms: 追加的完全 Bypass 關鍵詞（字串匹配）。
            custom_soft_terms: 追加的軟 Bypass 關鍵詞（字串匹配）。
            enabled: 是否啟用 Bypass 策略。
        """
        self._full_patterns = [
            re.compile(p) for p in (full_bypass_patterns or self.FULL_BYPASS_PATTERNS)
        ]
        self._soft_patterns = [
            re.compile(p) for p in (soft_bypass_patterns or self.SOFT_BYPASS_PATTERNS)
        ]
        self._custom_full: list[str] = custom_full_terms or []
        self._custom_soft: list[str] = custom_soft_terms or []
        self.enabled = enabled

        # 統計
        self._bypass_counts: dict[str, int] = {
            BypassMode.FULL: 0,
            BypassMode.SOFT: 0,
            BypassMode.NONE: 0,
        }

    def evaluate(self, query: str) -> BypassMode:
        """評估查詢應使用的 Bypass 模式。

        Args:
            query: 使用者的輸入查詢。

        Returns:
            BypassMode：FULL / SOFT / NONE
        """
        if not self.enabled:
            return BypassMode.NONE

        # 完全 Bypass 優先檢查
        if self._matches_full(query):
            self._bypass_counts[BypassMode.FULL] += 1
            return BypassMode.FULL

        # 軟 Bypass 次要檢查
        if self._matches_soft(query):
            self._bypass_counts[BypassMode.SOFT] += 1
            return BypassMode.SOFT

        self._bypass_counts[BypassMode.NONE] += 1
        return BypassMode.NONE

    def should_bypass(self, query: str) -> bool:
        """快速判斷：是否需要完全跳過記憶查詢。"""
        return self.evaluate(query) == BypassMode.FULL

    def get_memory_weight(self, query: str) -> float:
        """根據 Bypass 模式，取得記憶查詢結果的權重。

        Returns:
            1.0 = 記憶全權重 (NONE 模式)
            0.4 = 低權重記憶輔助 (SOFT 模式)
            0.0 = 完全忽略記憶 (FULL 模式)
        """
        mode = self.evaluate(query)
        return {
            BypassMode.FULL: 0.0,
            BypassMode.SOFT: 0.4,
            BypassMode.NONE: 1.0,
        }[mode]

    def add_full_bypass_term(self, term: str) -> None:
        """動態新增完全 Bypass 關鍵詞。"""
        self._custom_full.append(term)

    def add_soft_bypass_term(self, term: str) -> None:
        """動態新增軟 Bypass 關鍵詞。"""
        self._custom_soft.append(term)

    def get_stats(self) -> dict:
        """取得 Bypass 觸發統計。"""
        total = sum(self._bypass_counts.values()) or 1
        return {
            "counts": dict(self._bypass_counts),
            "bypass_rate": round(
                (self._bypass_counts[BypassMode.FULL] + self._bypass_counts[BypassMode.SOFT])
                / total,
                3,
            ),
            "full_bypass_rate": round(self._bypass_counts[BypassMode.FULL] / total, 3),
        }

    def _matches_full(self, query: str) -> bool:
        """檢查是否觸發完全 Bypass（正則 + 自訂詞）。"""
        for pattern in self._full_patterns:
            if pattern.search(query):
                return True
        return any(term in query for term in self._custom_full)

    def _matches_soft(self, query: str) -> bool:
        """檢查是否觸發軟 Bypass（正則 + 自訂詞）。"""
        for pattern in self._soft_patterns:
            if pattern.search(query):
                return True
        return any(term in query for term in self._custom_soft)


# 模組級別預設實例
_default_policy: Optional[MemoryBypassPolicy] = None


def get_bypass_policy() -> MemoryBypassPolicy:
    """取得模組預設的 MemoryBypassPolicy 實例。"""
    global _default_policy
    if _default_policy is None:
        _default_policy = MemoryBypassPolicy()
    return _default_policy
