"""LLM-driven memory summarization and sentiment analysis.

This module uses the Ollama LLM to automatically generate for each new memory:
- L1 summary (one sentence)
- L0 tag (short label)
- Sentiment polarity marker
"""

import json
import httpx


async def summarize(content: str, model: str, base_url: str = "http://localhost:11434") -> tuple[str, str, str]:
    """Call the LLM to generate memory summaries and sentiment markers.

    Args:
        content: Full conversation or memory content.
        model: Ollama model name.
        base_url: Ollama API endpoint.

    Returns:
        (l1_summary, l0_tag, sentiment) tuple.
        l1_summary: One-sentence summary.
        l0_tag: Keyword tag (max 3 words).
        sentiment: positive / negative / neutral / mixed.
    """
    prompt = f"""Analyze the following conversation content and return a JSON object (no markdown) with three fields:
- "l1": A one-sentence summary of the main point in **ENGLISH** (max 50 words).
- "l0": A descriptive keyword tag for the theme in **ENGLISH** (max 3 words).
- "sentiment": The emotional polarity, must be one of: positive, negative, neutral, mixed.

**Crucial: Even if the input content is in Chinese, you MUST output the 'l1' and 'l0' fields in ENGLISH.**

Content:
{content}

Return ONLY the JSON object:"""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=120.0,
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()

            # Clean common markdown wrappers
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                raw = "\n".join(lines).strip()

            data = json.loads(raw)
            l1 = str(data.get("l1", content[:50] + "..."))[:100]
            l0 = str(data.get("l0", "conversation"))[:20]
            sentiment = str(data.get("sentiment", "neutral")).lower()
            if sentiment not in ("positive", "negative", "neutral", "mixed"):
                sentiment = "neutral"
            return l1, l0, sentiment

        except Exception:
            # Fallback: simple truncation
            return content[:50] + "...", "conversation", "neutral"
