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


async def batch_validate_low_confidence(
    store,
    model: str,
    base_url: str = "http://localhost:11434",
    confidence_threshold: float = 0.50,
    batch_size: int = 20,
) -> dict:
    """事後批次核查：對低信心值記憶進行 LLM 事實驗證。

    修復問題 #1，#2：
    - #1: LLM Hallucination 可能被永久記錄，需要事後驗算
    - #2: 缺乏 Fact-check Layer，所有記憶信心值平等

    工作流程：
    1. 取出 confidence < threshold 的活躍記憶
    2. 對每條記憶，找 3 條最相似的「高信心值」記憶
    3. 由 LLM 判斷低信心記憶是否與高信心記憶矛盾或無法被支撐
    4. 若無任何高信心記憶支撐 → 降低信心值；若存在矛盾 → 標記衝突

    Args:
        store: MemoryStore 實例。
        model: Ollama 模型名稱。
        base_url: Ollama API 地址。
        confidence_threshold: 低於此值的記憶視為「待核查」。
        batch_size: 每次最多處理的記憶數量。

    Returns:
        核查報告，包含降級數量、衝突標記數量。
    """
    from ..models import MemoryStatus

    # 取出所有低信心值的活躍記憶
    all_memories = await store.list_all(limit=1000)
    candidates = [
        m for m in all_memories
        if m.status == MemoryStatus.ACTIVE
        and m.confidence < confidence_threshold
        and not m.metadata.get("_fact_checked")  # 避免重複檢查
    ][:batch_size]

    downgraded = 0
    conflicts_found = 0

    for memory in candidates:
        # 找相似的「高信心值」記憶作為參照
        try:
            similar = await store.search_similar(
                memory.content, limit=3, min_importance=0.0
            )
            high_confidence_refs = [
                m for m in similar
                if m.id != memory.id and m.confidence >= 0.75
            ]
        except Exception:
            continue

        if not high_confidence_refs:
            # 無任何高信心記憶支撐 → 輕微降低信心值
            memory.confidence = max(0.05, memory.confidence * 0.85)
            memory.metadata["_fact_checked"] = True
            memory.metadata["_fact_check_result"] = "unsupported"
            await store.update(memory)
            downgraded += 1
            continue

        # LLM 核查：此記憶是否與高信心參照矛盾？
        conflict_id = await check_conflicts(
            memory.content, high_confidence_refs, model, base_url
        )

        if conflict_id:
            # 標記衝突
            memory.conflict_with = conflict_id
            memory.confidence = max(0.05, memory.confidence * 0.70)
            memory.metadata["_fact_checked"] = True
            memory.metadata["_fact_check_result"] = "conflicted"
            await store.update(memory)
            conflicts_found += 1
        else:
            # 通過核查 → 輕微提升信心值
            memory.confidence = min(0.90, memory.confidence * 1.10)
            memory.metadata["_fact_checked"] = True
            memory.metadata["_fact_check_result"] = "validated"
            await store.update(memory)

    return {
        "candidates_checked": len(candidates),
        "downgraded": downgraded,
        "conflicts_found": conflicts_found,
        "validated": len(candidates) - downgraded - conflicts_found,
    }
