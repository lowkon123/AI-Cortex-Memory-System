"""LLM 驅動的知識萃取模組。

從對話內容中自動提取關於使用者的持久性事實
（例如姓名、地點、偏好等），每個事實會被存為高重要性記憶。
"""

import json
import httpx


async def extract_facts(content: str, model: str, base_url: str = "http://localhost:11434") -> list[str]:
    """從對話內容中萃取使用者的個人事實。

    Args:
        content: 完整的對話內容。
        model: Ollama 模型名稱。
        base_url: Ollama API 地址。

    Returns:
        事實字串列表。如果沒有可萃取的事實，回傳空列表。
    """
    prompt = f"""請仔細閱讀以下對話，提取其中任何關於「使用者」本人的個人事實。
事實包括但不限於：姓名、暱稱、居住地、職業、年齡、喜好、習慣、計畫、重要日期等。

規則：
- 只提取明確陳述的事實，不要推測
- 每個事實用一句簡短的繁體中文描述
- 如果對話中沒有任何個人事實，回傳空陣列
- 直接回傳 JSON 陣列，不要有其他文字

對話內容：
{content}

請直接回傳 JSON 陣列："""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=120.0,
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()

            # 清理 markdown 包裝
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                raw = "\n".join(lines).strip()

            facts = json.loads(raw)
            if isinstance(facts, list):
                return [str(f) for f in facts if f and str(f).strip()]
            return []

        except Exception:
            return []
