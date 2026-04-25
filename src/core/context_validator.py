"""Context Validator — Scenario applicability verification layer.

Fixes #7: Lack of "scenario fit" verification after storing memories, 
leading to incorrect citations across context—e.g., backend design 
decisions applied to frontend issues.

This module evaluates the fit of each recalled memory against the 
current query scenario, filtering out "technically relevant but 
actually inapplicable" memories.
"""

from __future__ import annotations

import json
from typing import Optional

import httpx
import numpy as np

from ..models import MemoryNode


class ContextValidator:
    """Validates if a memory fits the current query scenario.

    Context Validation Modes:
    1. Vector-based (Fast, low cost): Cosine similarity pruning.
    2. LLM-based (High cost): Detailed judging of scenario compatibility.
    """

    def __init__(
        self,
        min_context_score: float = 0.55,
        llm_model: Optional[str] = None,
        llm_base_url: str = "http://localhost:11434",
        use_llm_validation: bool = False,
    ):
        """Initialize ContextValidator.

        Args:
            min_context_score: Threshold for scenario fit score.
            llm_model: Ollama model name for LLM validation.
            llm_base_url: Ollama API endpoint.
            use_llm_validation: Whether to enable LLM-based validation.
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
        """Evaluate scenario fit using vector cosine similarity."""
        if not memory.embedding or not query_vector:
            return 0.5

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
        """Fast vector filtering to remove inapplicable memories."""
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
        """Deep scenario fit evaluation using LLM."""
        if not self.llm_model:
            return 0.7

        memory_text = memory.summary_l1 or memory.content[:200]
        prompt = f"""You are a Memory Scenario Validator. Evaluate if the following "Memory Snippet" is suitable for answering the "Current Question".

Current Question/Scenario:
{current_context}

Memory Snippet:
{memory_text}

Return a JSON object (no markdown):
- "applicable": true or false
- "score": 0.0 to 1.0 (suitability score)
- "reason": A one-sentence explanation

Return ONLY the JSON:"""

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
            return 0.7

    async def filter_memories(
        self,
        memories: list[MemoryNode],
        current_context: str,
        query_vector: Optional[list[float]] = None,
    ) -> list[MemoryNode]:
        """Full validation flow: vector pruning followed by optional LLM deep validation."""
        # Step 1: Fast vector filter
        if query_vector:
            memories = self.filter_by_vector(memories, query_vector)

        if not self.use_llm_validation or not self.llm_model:
            return memories

        # Step 2: LLM deep validation
        validated = []
        for memory in memories:
            llm_score = await self.validate_by_llm(memory, current_context)
            memory.metadata["_llm_context_score"] = round(llm_score, 4)
            if llm_score >= self.min_context_score:
                validated.append(memory)

        return validated

    def explain(self, memory: MemoryNode) -> dict:
        """Retrieve scenario validation results from metadata."""
        return {
            "vector_score": memory.metadata.get("_context_score"),
            "llm_score": memory.metadata.get("_llm_context_score"),
            "applicable": (
                (memory.metadata.get("_context_score", 0) >= self.min_context_score)
                or (memory.metadata.get("_llm_context_score", 0) >= self.min_context_score)
            ),
        }
