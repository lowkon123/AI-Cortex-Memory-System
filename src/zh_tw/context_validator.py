"""Context Validator — 場景適用性驗證層。

修復問題 #7：記憶存入後缺乏「場景吻合度」驗證，
導致錯誤場景的記憶被誤引用——例如後端設計決策被用於前端問題。

此模組在記憶召回後，對每條記憶評估其與當前查詢場景的吻合度，
並過濾掉場景不匹配的「技術上相關但實際上不適用」的記憶。
"""

from __future__ import annotations

import json
from typing import Optional

import httpx
import numpy as np

from ..models import MemoryNode


class ContextValidator:
    """驗證記憶是否適合當前查詢場景。

    提供兩種驗證模式：
    1. 向量快速驗證（無 LLM，低成本）：基於 Query 向量與記憶向量的相似度剪枝
    2. LLM 深度驗證（高成本）：讓 LLM 判斷記憶是否與當前任務場景兼容
    """

    def __init__(
        self,
        min_context_score: float = 0.55,
        llm_model: Optional[str] = None,
        llm_base_url: str = "http://localhost:11434",
        use_llm_validation: bool = False,
    ):
        """初始化 Context Validator。

        Args:
            min_context_score: 場景吻合分數門檻（低於此值的記憶被過濾）。
            llm_model: Ollama 模型名稱（LLM 驗證模式使用）。
            llm_base_url: Ollama API 地址。
            use_llm_validation: 是否啟用 LLM 深度驗證（成本較高）。
        """
        self.min_context_score = min_context_score
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.use_llm_validation = use_llm_validation

    def score_by_vector(
        self,
        memory: MemoryNode,
        query_vector: list[float],
    ) -> float:
        """使用向量餘弦相似度快速評估場景吻合度。

        Args:
            memory: 被驗證的記憶節點。
            query_vector: 當前查詢的向量。

        Returns:
            0.0–1.0 的場景吻合分數。
        """
        if not memory.embedding or not query_vector:
            return 0.5  # 無向量時中性分數

        q = np.array(query_vector, dtype=np.float32)
        m = np.array(memory.embedding, dtype=np.float32)
        qn, mn = np.linalg.norm(q), np.linalg.norm(m)
        if qn == 0 or mn == 0:
            return 0.5
        cosine = float(np.dot(q / qn, m / mn))
        return max(0.0, min(1.0, (cosine + 1) / 2))

    def filter_by_vector(
        self,
        memories: list[MemoryNode],
        query_vector: list[float],
        min_score: Optional[float] = None,
    ) -> list[MemoryNode]:
        """快速向量過濾：移除場景不吻合的記憶（無 LLM 開銷）。

        Args:
            memories: 要過濾的記憶列表。
            query_vector: 當前查詢向量。
            min_score: 覆蓋預設門檻。

        Returns:
            場景吻合的記憶列表。
        """
        threshold = min_score if min_score is not None else self.min_context_score
        result = []
        for m in memories:
            score = self.score_by_vector(m, query_vector)
            m.metadata["_context_score"] = round(score, 4)
            if score >= threshold:
                result.append(m)
        return result

    async def validate_by_llm(
        self,
        memory: MemoryNode,
        current_context: str,
    ) -> float:
        """使用 LLM 深度評估記憶與當前場景的吻合度。

        Args:
            memory: 被驗證的記憶節點。
            current_context: 當前對話的場景描述或問題文字。

        Returns:
            0.0–1.0 的吻合分數（0 = 完全不適用，1 = 高度適用）。
        """
        if not self.llm_model:
            return 0.7  # 無模型時給中性分數

        memory_text = memory.summary_l1 or memory.content[:200]
        prompt = f"""你是一個記憶場景驗證器。請評估以下「記憶片段」是否適合用來回答「當前問題」。

當前問題/場景：
{current_context}

記憶片段：
{memory_text}

請只回傳一個 JSON 物件（不要 markdown 格式）：
- "applicable": true 或 false
- "score": 0.0 到 1.0 的數字，代表適用程度
- "reason": 一句話解釋

直接回傳 JSON："""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.llm_base_url}/api/generate",
                    json={"model": self.llm_model, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                response.raise_for_status()
                raw = response.json()["response"].strip()
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    lines = [l for l in lines if not l.startswith("```")]
                    raw = "\n".join(lines).strip()
                data = json.loads(raw)
                score = float(data.get("score", 0.7))
                return max(0.0, min(1.0, score))
        except Exception:
            return 0.7  # LLM 失敗時給中性分數

    async def filter_memories(
        self,
        memories: list[MemoryNode],
        current_context: str,
        query_vector: Optional[list[float]] = None,
    ) -> list[MemoryNode]:
        """完整驗證流程：先向量篩選，可選追加 LLM 深度驗證。

        Args:
            memories: 待驗證的記憶列表。
            current_context: 當前問題/場景文字。
            query_vector: 當前查詢向量（可選）。

        Returns:
            通過場景驗證的記憶列表，並將分數寫入 metadata。
        """
        # Step 1: 向量快速過濾（低成本）
        if query_vector:
            memories = self.filter_by_vector(memories, query_vector)

        if not self.use_llm_validation or not self.llm_model:
            return memories

        # Step 2: LLM 深度驗證（可選，高成本）
        validated = []
        for memory in memories:
            llm_score = await self.validate_by_llm(memory, current_context)
            memory.metadata["_llm_context_score"] = round(llm_score, 4)
            if llm_score >= self.min_context_score:
                validated.append(memory)

        return validated

    def explain(self, memory: MemoryNode) -> dict:
        """讀取記憶的場景驗證結果（從 metadata）。"""
        return {
            "vector_score": memory.metadata.get("_context_score"),
            "llm_score": memory.metadata.get("_llm_context_score"),
            "applicable": (
                (memory.metadata.get("_context_score", 0) >= self.min_context_score)
                or (memory.metadata.get("_llm_context_score", 0) >= self.min_context_score)
            ),
        }
