"""Query Reformer — Query rewriting and semantic expansion layer.

Fixes #12: High query sensitivity (different phrasings leading to different results).
Mitigates #11: Semantic bias in embedding search.

When a user's input is semantically vague or uses specific jargon, 
this module generates multiple semantically equivalent variants 
through synonym expansion, clause splitting, and rephrasing. 
These are used in Multi-intent search to improve retrieval stability and recall.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import httpx


class QueryReformer:
    """Rewrites user queries into multiple semantically equivalent variants.

    Strategies:
    1. Rule-based (Fast, no LLM): Synonym replacement, voice conversion.
    2. LLM-based (High quality): Generates 3 phrased variants with identical meaning.
    3. Hybrid: Rules first, then LLM if results are insufficient.
    """

    # Common synonym groups for fast rule-based rewriting
    SYNONYM_GROUPS: list[list[str]] = [
        ["like", "prefer", "habit", "love"],
        ["project", "plan", "task", "assignment"],
        ["problem", "error", "bug", "exception", "issue"],
        ["user", "resident", "client"],
        ["database", "db", "storage"],
        ["function", "feature", "capability"],
        ["deploy", "release", "launch"],
        ["setup", "config", "configuration", "settings"],
    ]

    def __init__(
        self,
        llm_model: Optional[str] = None,
        llm_base_url: str = "http://localhost:11434",
        max_variants: int = 3,
        use_llm: bool = True,
    ):
        """Initialize QueryReformer.

        Args:
            llm_model: Ollama model name for LLM rewriting.
            llm_base_url: Ollama API endpoint.
            max_variants: Maximum variants to generate (including original).
            use_llm: Whether to enable LLM-based rewriting.
        """
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.max_variants = max_variants
        self.use_llm = use_llm

        # Prebuild synonym map
        self._synonym_map: dict[str, list[str]] = {}
        for group in self.SYNONYM_GROUPS:
            for word in group:
                self._synonym_map[word] = [w for w in group if w != word]

    def reform_by_rules(self, query: str) -> list[str]:
        """Fast rule-based rewriting: use synonym replacement (no LLM).

        Args:
            query: Original query string.

        Returns:
            List of rewritten variants including original.
        """
        variants = [query]
        query_lower = query.lower()

        for word, synonyms in self._synonym_map.items():
            if word in query_lower:
                for syn in synonyms[:1]:  # Replace one at a time to avoid explosion
                    # Preserve original case if possible or just use lower for simplicity
                    variant = query_lower.replace(word, syn, 1)
                    if variant not in [v.lower() for v in variants]:
                        variants.append(variant)
                        if len(variants) >= self.max_variants:
                            return variants

        return variants

    def split_compound_query(self, query: str) -> list[str]:
        """Split complex questions into multiple sub-queries.

        Example: "Tell me about user habits and project progress"
        -> ["user habits", "project progress"]

        Args:
            query: Query potentially containing multiple intents.

        Returns:
            List of sub-queries.
        """
        connectors = [r" and ", r" as well as ", r" also ", r" plus ", r" & "]
        pattern = "|".join(connectors)
        parts = re.split(pattern, query, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if len(p.strip()) > 3]

        if len(parts) <= 1:
            return [query]
        return parts

    async def reform_by_llm(self, query: str) -> list[str]:
        """Use LLM to rewrite query: generate phrase variants with identical meaning.

        Args:
            query: Original query string.

        Returns:
            List of variants including original.
        """
        if not self.llm_model:
            return [query]

        prompt = f"""Rewrite the following search query into 2 semantically identical versions with different phrasing.
The goal is to improve semantic search stability.

Original Query: {query}

Rules:
- Maintain exact semantic meaning.
- Use different vocabulary or sentence structure.
- Output in English.
- Return ONLY a JSON string array, e.g., ["version1", "version2"]

Return ONLY the JSON:"""

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
        """Full expansion flow: rules + splitting + optional LLM rewriting.

        Args:
            query: Original query string.

        Returns:
            Deduplicated list of variants, up to max_variants.
        """
        all_variants: list[str] = [query]

        # Step 1: Split compound sentences
        sub_queries = self.split_compound_query(query)
        for sq in sub_queries:
            if sq not in all_variants:
                all_variants.append(sq)

        # Step 2: Synonym rule rewriting
        rule_variants = self.reform_by_rules(query)
        for v in rule_variants:
            if v not in all_variants:
                all_variants.append(v)

        # Step 3: LLM rewriting (if enabled and fewer than target variants)
        if self.use_llm and self.llm_model and len(all_variants) < self.max_variants:
            llm_variants = await self.reform_by_llm(query)
            for v in llm_variants:
                if v not in all_variants:
                    all_variants.append(v)

        return all_variants[: self.max_variants]

    def get_stable_query(self, query: str) -> str:
        """Normalize query (remove filler words, punctuation) for stability.

        Fixes #12: Phrasings of the same question should yield consistent results.
        """
        filler_words = ["um", "err", "well", "actually", "just", "please", "can you tell me"]
        stable = query.lower()
        for filler in filler_words:
            stable = stable.replace(filler, "").strip()

        # Normalize punctuation
        stable = re.sub(r"[?!,.]+$", "", stable).strip()
        return stable if stable else query
