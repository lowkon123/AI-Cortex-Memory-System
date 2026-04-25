"""Conflict Detector — Automatic identification of semantic contradictions.

When a new memory is stored, it is compared with the most semantically 
similar existing memories. An LLM determines if there is a factual 
contradiction between them.
"""

import json
import httpx
from typing import Optional
from uuid import UUID

from ..models import MemoryNode


async def check_conflicts(new_content: str, similar_memories: list[MemoryNode],
                          model: str, base_url: str = "http://localhost:11434") -> Optional[UUID]:
    """Check if a new memory contradicts existing memories.

    Args:
        new_content: Content of the new memory.
        similar_memories: List of semantically similar existing memories.
        model: Ollama model name.
        base_url: Ollama API endpoint.

    Returns:
        UUID of the conflicting memory, or None if no conflict is found.
    """
    if not similar_memories:
        return None

    memories_text = ""
    for i, m in enumerate(similar_memories[:3]):
        memories_text += f"\nMemory {i+1} (ID: {m.id}):\n{m.summary_l1 or m.content[:100]}\n"

    prompt = f"""Determine if the "New Memory" contradicts any of the "Old Memories" below.
Contradiction Definition: Two memories state opposing facts about the same subject (e.g., "Likes coffee" vs "Does not drink coffee").

New Memory:
{new_content[:200]}

Old Memories:
{memories_text}

Return a JSON object (no markdown):
- "has_conflict": true or false
- "conflict_id": If there is a conflict, the ID of the old memory (string); otherwise null

Return ONLY the JSON:"""

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
    """Post-hoc batch verification: Use LLM to fact-check low-confidence memories.

    Fixes #1, #2:
    - #1: LLM Hallucinated memories need post-hoc verification.
    - #2: Lack of Fact-check Layer; all memory confidence levels were equal.

    Workflow:
    1. Fetch active memories with confidence < threshold.
    2. For each, find the 3 most similar "high-confidence" memories.
    3. Use LLM to judge if the low-confidence memory is contradicted or unsupported.
    4. If no high-confidence support -> decrease confidence; if contradiction -> mark conflict.

    Args:
        store: MemoryStore instance.
        model: Ollama model name.
        base_url: Ollama API endpoint.
        confidence_threshold: Memories below this value are considered "pending verification".
        batch_size: Maximum number of memories to process in one batch.

    Returns:
        Verification report with counts of downgraded, conflicted, and validated memories.
    """
    from ..models import MemoryStatus

    # Fetch active low-confidence memories
    all_memories = await store.list_all(limit=1000)
    candidates = [
        m for m in all_memories
        if m.status == MemoryStatus.ACTIVE
        and m.confidence < confidence_threshold
        and not m.metadata.get("_fact_checked")  # Avoid redundant checks
    ][:batch_size]

    downgraded = 0
    conflicts_found = 0

    for memory in candidates:
        # Find similar high-confidence memories as reference
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
            # No high-confidence support -> slightly decrease confidence
            memory.confidence = max(0.05, memory.confidence * 0.85)
            memory.metadata["_fact_checked"] = True
            memory.metadata["_fact_check_result"] = "unsupported"
            await store.update(memory)
            downgraded += 1
            continue

        # LLM Fact-check: Does this contradict high-confidence references?
        conflict_id = await check_conflicts(
            memory.content, high_confidence_refs, model, base_url
        )

        if conflict_id:
            # Mark as conflicted
            memory.conflict_with = conflict_id
            memory.confidence = max(0.05, memory.confidence * 0.70)
            memory.metadata["_fact_checked"] = True
            memory.metadata["_fact_check_result"] = "conflicted"
            await store.update(memory)
            conflicts_found += 1
        else:
            # Passed verification -> slightly increase confidence
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
