"""Query Reformer — 查詢改寫與語意擴展層。

修復問題 #12：Query 敏感度太高（問法不同結果完全不同）
修復問題 #11：Embedding 搜尋語意偏差輔助緩解

當使用者輸入的 Query 語意模糊或用詞特殊時，
此模組透過同義詞擴展、子句拆分、重新措辭等手段
生成多個語意等效的變體，送入 Multi-intent 搜尋，
大幅提升 Retrieval 的穩定性與召回率。
"""

from __future__ import annotations

import json
import re
from typing import Optional

import httpx


class QueryReformer:
    """將使用者原始查詢改寫為多個語意等效變體。

    策略：
    1. 規則改寫（快速，無 LLM）：同義詞替換、語態轉換
    2. LLM 改寫（高品質）：讓 LLM 生成 3 個措辭不同但語意相同的版本
    3. 混合模式：先規則，若結果過少再用 LLM 补充
    """

    # 常見同義詞群組（用於快速規則改寫）
    SYNONYM_GROUPS: list[list[str]] = [
        ["喜歡", "偏好", "習慣", "愛用"],
        ["專案", "項目", "計畫", "project"],
        ["問題", "錯誤", "bug", "exception", "issue"],
        ["使用者", "用戶", "user"],
        ["資料庫", "database", "DB"],
        ["功能", "feature", "特性"],
        ["部署", "上線", "deploy", "release"],
        ["設定", "配置", "config", "configuration"],
    ]

    def __init__(
        self,
        llm_model: Optional[str] = None,
        llm_base_url: str = "http://localhost:11434",
        max_variants: int = 3,
        use_llm: bool = True,
    ):
        """初始化 QueryReformer。

        Args:
            llm_model: Ollama 模型名稱（LLM 改寫使用）。
            llm_base_url: Ollama API 地址。
            max_variants: 最多生成幾個變體（含原始查詢）。
            use_llm: 是否啟用 LLM 改寫。
        """
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.max_variants = max_variants
        self.use_llm = use_llm

        # 預建同義詞映射
        self._synonym_map: dict[str, list[str]] = {}
        for group in self.SYNONYM_GROUPS:
            for word in group:
                self._synonym_map[word] = [w for w in group if w != word]

    def reform_by_rules(self, query: str) -> list[str]:
        """快速規則改寫：用同義詞替換生成變體（無 LLM）。

        Args:
            query: 原始查詢字串。

        Returns:
            包含原始查詢的改寫變體列表。
        """
        variants = [query]

        for word, synonyms in self._synonym_map.items():
            if word in query:
                for syn in synonyms[:1]:  # 每次只換一個同義詞，避免爆炸
                    variant = query.replace(word, syn, 1)
                    if variant not in variants:
                        variants.append(variant)
                        if len(variants) >= self.max_variants:
                            return variants

        return variants

    def split_compound_query(self, query: str) -> list[str]:
        """將複合問題拆分成多個子查詢。

        例：「告訴我用戶的習慣和專案進度」
        → [「用戶習慣」, 「專案進度」]

        Args:
            query: 可能包含多個意圖的查詢。

        Returns:
            子查詢列表。
        """
        # 拆分連接詞
        connectors = [r"和", r"以及", r"還有", r"加上", r"與", r"&", r"and"]
        pattern = "|".join(connectors)
        parts = re.split(pattern, query)
        parts = [p.strip() for p in parts if len(p.strip()) > 3]

        if len(parts) <= 1:
            return [query]
        return parts

    async def reform_by_llm(self, query: str) -> list[str]:
        """用 LLM 改寫查詢：生成措辭不同但語意相同的變體。

        Args:
            query: 原始查詢字串。

        Returns:
            包含原始查詢在內的改寫變體列表。
        """
        if not self.llm_model:
            return [query]

        prompt = f"""請將以下查詢改寫成 2 個「語意完全相同，但措辭不同」的版本。
目的是提升語意搜尋的穩定性。

原始查詢：{query}

規則：
- 保持語意完全一致
- 使用不同的詞彙或句式
- 繁體中文輸出
- 直接回傳 JSON 字串陣列，例如：["版本1", "版本2"]

直接回傳 JSON："""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.llm_base_url}/api/generate",
                    json={"model": self.llm_model, "prompt": prompt, "stream": False},
                    timeout=20.0,
                )
                response.raise_for_status()
                raw = response.json()["response"].strip()
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    raw = "\n".join([l for l in lines if not l.startswith("```")]).strip()
                variants = json.loads(raw)
                if isinstance(variants, list):
                    return [query] + [str(v) for v in variants if v and str(v) != query]
        except Exception:
            pass

        return [query]

    async def expand(self, query: str) -> list[str]:
        """完整擴展流程：規則 + 子句拆分 + 可選 LLM 改寫。

        Args:
            query: 原始查詢字串。

        Returns:
            去重後的查詢變體列表（含原始），最多 max_variants 個。
        """
        all_variants: list[str] = [query]

        # Step 1: 拆複合句
        sub_queries = self.split_compound_query(query)
        for sq in sub_queries:
            if sq not in all_variants:
                all_variants.append(sq)

        # Step 2: 同義詞規則改寫
        rule_variants = self.reform_by_rules(query)
        for v in rule_variants:
            if v not in all_variants:
                all_variants.append(v)

        # Step 3: LLM 改寫（若啟用且變體少於目標數量）
        if self.use_llm and self.llm_model and len(all_variants) < self.max_variants:
            llm_variants = await self.reform_by_llm(query)
            for v in llm_variants:
                if v not in all_variants:
                    all_variants.append(v)

        return all_variants[: self.max_variants]

    def get_stable_query(self, query: str) -> str:
        """標準化查詢（去除口語化詞彙、標點），提升搜尋穩定性。

        修復 #12：不同說法的同一問題應取得一致結果。
        """
        # 去除常見語氣詞
        filler_words = ["嗯", "呃", "那個", "就是", "幫我", "請問", "可以告訴我"]
        stable = query
        for filler in filler_words:
            stable = stable.replace(filler, "").strip()

        # 標準化標點
        stable = re.sub(r"[？?！!，,。.]+$", "", stable).strip()
        return stable if stable else query
