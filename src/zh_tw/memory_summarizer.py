"""LLM 驅動的記憶摘要與情緒分析。

此模組使用 Ollama LLM 為每筆新記憶自動產生：
- L1 摘要（一句話）
- L0 標籤（3 字以內）
- 情緒極性標記
"""

import json
import httpx


async def summarize(content: str, model: str, base_url: str = "http://localhost:11434") -> tuple[str, str, str]:
    """呼叫 LLM 生成記憶摘要與情緒標記。

    Args:
        content: 完整的對話內容。
        model: Ollama 模型名稱。
        base_url: Ollama API 地址。

    Returns:
        (l1_summary, l0_tag, sentiment) 元組。
        l1_summary: 一句話摘要。
        l0_tag: 3 字以內的關鍵詞標籤。
        sentiment: positive / negative / neutral / mixed。
    """
    prompt = f"""請分析以下對話內容，回傳一個 JSON 物件（不要加 markdown 格式），包含三個欄位：
- "l1": 用一句繁體中文摘要這段對話的重點（不超過 50 字）
- "l0": 用最多 3 個字的繁體中文關鍵詞標籤描述主題
- "sentiment": 這段對話的情緒極性，只能是 positive / negative / neutral / mixed 其中之一

對話內容：
{content}

請直接回傳 JSON，不要有任何其他文字："""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=120.0,
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()

            # 嘗試清理常見的 markdown 包裝
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                raw = "\n".join(lines).strip()

            data = json.loads(raw)
            l1 = str(data.get("l1", content[:50] + "..."))[:100]
            l0 = str(data.get("l0", "對話"))[:10]
            sentiment = str(data.get("sentiment", "neutral")).lower()
            if sentiment not in ("positive", "negative", "neutral", "mixed"):
                sentiment = "neutral"
            return l1, l0, sentiment

        except Exception:
            # 回退：使用截斷方式
            return content[:50] + "...", "對話", "neutral"
