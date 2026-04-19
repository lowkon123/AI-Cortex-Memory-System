"""記憶衝突偵測器 — 語義矛盾自動識別。

當新記憶存入時，與語義最相似的舊記憶進行比對，
透過 LLM 判斷兩者是否存在事實矛盾。
"""

import json
import httpx
from typing import Optional
from uuid import UUID

from ..models import MemoryNode


async def check_conflicts(new_content: str, similar_memories: list[MemoryNode],
                          model: str, base_url: str = "http://localhost:11434") -> Optional[UUID]:
    """檢查新記憶是否與現有記憶衝突。

    Args:
        new_content: 新記憶的內容。
        similar_memories: 語義最相似的舊記憶列表。
        model: Ollama 模型名稱。
        base_url: Ollama API 地址。

    Returns:
        衝突記憶的 UUID，若無衝突則為 None。
    """
    if not similar_memories:
        return None

    memories_text = ""
    for i, m in enumerate(similar_memories[:3]):
        memories_text += f"\n記憶 {i+1} (ID: {m.id}):\n{m.summary_l1 or m.content[:100]}\n"

    prompt = f"""請判斷「新記憶」是否與以下任何一筆「舊記憶」存在事實矛盾。
矛盾的定義：兩段記憶對同一件事的陳述相互抵觸（例如「喜歡咖啡」vs「不喝咖啡」）。

新記憶：
{new_content[:200]}

舊記憶：
{memories_text}

請回傳一個 JSON 物件（不要 markdown 格式）：
- "has_conflict": true 或 false
- "conflict_id": 如果有衝突，填入衝突的舊記憶 ID（字串）；否則填 null

直接回傳 JSON："""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60.0,
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()

            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                raw = "\n".join(lines).strip()

            data = json.loads(raw)
            if data.get("has_conflict") and data.get("conflict_id"):
                return UUID(str(data["conflict_id"]))
            return None

        except Exception:
            return None
