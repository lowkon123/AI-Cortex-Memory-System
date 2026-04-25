"""Background sleep-cycle maintenance for memories."""

from __future__ import annotations

import asyncio
import json
import httpx
import numpy as np

from .memory_forgetting import MemoryForgetting
from ..models import MemoryKind, MemoryNode, MemorySource, MemoryStatus, utc_now

# Ollama model used for episode consolidation (inherits from dashboard env or default)
CONSOLIDATE_MODEL = "llama3"
CONSOLIDATE_BASE_URL = "http://localhost:11434"

LAST_SLEEP_REPORT = {
    "ran_at": None,
    "processed": 0,
    "updated": 0,
    "archived": 0,
    "forgotten": 0,
    "compressed": 0,
    "consolidated": 0,
}


async def run_sleep_cycle(store, interval_hours: int = 6) -> None:
    """Run periodic memory maintenance tasks."""
    from .metabolism import MemoryMetabolism
    metabolism = MemoryMetabolism(stability_factor=48.0)

    while True:
        try:
            await asyncio.sleep(interval_hours * 3600)

            memories = await store.list_all(limit=1000)
            if not memories:
                LAST_SLEEP_REPORT.update({
                    "ran_at": utc_now().isoformat(),
                    "processed": 0, "updated": 0, "archived": 0, "forgotten": 0, "compressed": 0, "consolidated": 0
                })
                continue

            # 1. Metabolism (Decay & Status Update)
            modified = await metabolism.process_batch(memories)
            
            # 2. Deduplication (Merge highly similar memories)
            merged_count = await deduplicate_memories(store, memories)
            
            # 3. Abstraction (Turn Episode clusters into Knowledge)
            abstracted_count = await consolidate_episodes(store, memories)

            archived = 0
            forgotten = 0
            compressed = 0

            for memory in modified:
                await store.update(memory)
                if memory.status == MemoryStatus.ARCHIVED:
                    archived += 1
                elif memory.status == MemoryStatus.FORGOTTEN:
                    forgotten += 1
                elif memory.status == MemoryStatus.COMPRESSED:
                    compressed += 1

            LAST_SLEEP_REPORT.update({
                "ran_at": utc_now().isoformat(),
                "processed": len(memories),
                "updated": len(modified),
                "archived": archived,
                "forgotten": forgotten,
                "compressed": compressed,
                "merged": merged_count,
                "abstracted": abstracted_count,
            })

        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)


def get_last_sleep_report() -> dict:
    """Return the most recent background maintenance summary."""
    return LAST_SLEEP_REPORT.copy()


async def deduplicate_memories(store, memories: list[MemoryNode]) -> int:
    """Find highly similar memories and merge them into the more important one."""
    import numpy as np
    
    merged = 0
    to_delete = set()
    
    # Simple O(n^2) check for small batches, can be optimized later
    for i in range(len(memories)):
        if memories[i].id in to_delete:
            continue
        for j in range(i + 1, len(memories)):
            if memories[j].id in to_delete:
                continue
            
            if memories[i].embedding and memories[j].embedding:
                # Cosine similarity
                vec_i = np.array(memories[i].embedding)
                vec_j = np.array(memories[j].embedding)
                dot = np.dot(vec_i, vec_j)
                norm_i = np.linalg.norm(vec_i)
                norm_j = np.linalg.norm(vec_j)
                similarity = dot / (norm_i * norm_j) if norm_i > 0 and norm_j > 0 else 0
                
                if similarity > 0.96:
                    # Merge J into I
                    memories[i].importance = max(memories[i].importance, memories[j].importance)
                    memories[i].access_count += memories[j].access_count
                    memories[i].concept_tags = list(set(memories[i].concept_tags) | set(memories[j].concept_tags))
                    
                    to_delete.add(memories[j].id)
                    merged += 1
                    
        if memories[i].id not in to_delete:
            await store.update(memories[i])
            
    for m_id in to_delete:
        await store.delete(m_id)
        
    return merged


async def consolidate_episodes(store, memories: list[MemoryNode]) -> int:
    """LLM-driven abstraction: cluster episodic memories into structured Facts.

    Process:
    1. Select recent EPISODIC memories with high access count or importance.
    2. Group them by concept_tags overlap (simple clustering).
    3. For each cluster, call LLM to extract a distilled FACT memory.
    4. Store new FACT node and link with SUPPORTS relation.
    """
    # Only process episodic memories that are candidates for consolidation
    candidates = [
        m for m in memories
        if m.memory_kind == MemoryKind.EPISODIC
        and m.status == MemoryStatus.ACTIVE
        and m.consolidation_count < 3
        and (m.access_count >= 2 or m.importance >= 0.7)
    ]

    if len(candidates) < 3:
        return 0  # Not enough episodes to form a meaningful cluster

    abstracted = 0

    # Simple clustering: group by shared concept_tags
    clusters: dict[str, list[MemoryNode]] = {}
    for memory in candidates:
        key = ",".join(sorted(memory.concept_tags[:2])) if memory.concept_tags else "_uncategorized"
        clusters.setdefault(key, []).append(memory)

    for cluster_key, cluster_members in clusters.items():
        if len(cluster_members) < 2:
            continue  # Skip singleton clusters

        # Prepare content for LLM distillation
        snippets = []
        for m in cluster_members[:5]:
            snippets.append(m.summary_l1 or m.content[:150])
        combined = "\n---\n".join(snippets)

        prompt = f"""You are a Cognitive Consolidation Agent. Your task is to distill a generalized "Semantic Fact" or "Rule" from a set of episodic conversation records.

Conversation records:
{combined}

Identify the core underlying concept, architecture decision, or user preference. Ignore transient details, pleasantries, or temporal markers (e.g., "today", "just now").
Return a JSON object:
- "fact": A clear, generalized factual statement or rule (English).
- "importance": Importance score 0.0-1.0 based on how likely this rule is needed in the future.
- "concept_tags": Max 3 keyword concept tags (array of strings).

Return ONLY the JSON:"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{CONSOLIDATE_BASE_URL}/api/generate",
                    json={"model": CONSOLIDATE_MODEL, "prompt": prompt, "stream": False},
                    timeout=60.0,
                )
                response.raise_for_status()
                raw = response.json()["response"].strip()
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    raw = "\n".join([l for l in lines if not l.startswith("```")]).strip()

                data = json.loads(raw)
                fact_content = data.get("fact", "").strip()
                if not fact_content:
                    continue

                # Create new FACT memory node
                new_fact = MemoryNode(
                    content=fact_content,
                    summary_l1=fact_content,
                    summary_l0=fact_content[:60] + ("..." if len(fact_content) > 60 else ""),
                    importance=float(data.get("importance", 0.7)),
                    memory_kind=MemoryKind.SEMANTIC,
                    source_type=MemorySource.INFERRED,
                    concept_tags=data.get("concept_tags", []),
                    metadata={"_consolidated_from": [str(m.id) for m in cluster_members]},
                )
                await store.insert(new_fact)

                # Batch mark source episodes as consolidated
                await store.mark_consolidated([m.id for m in cluster_members])

                abstracted += 1
                await asyncio.sleep(0.5)  # Prevent Ollama overload

        except Exception:
            continue

    return abstracted
