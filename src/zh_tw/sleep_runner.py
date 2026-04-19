"""Background sleep-cycle maintenance for memories."""

from __future__ import annotations

import asyncio

from .memory_forgetting import MemoryForgetting
from ..models import utc_now

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
    forgetting = MemoryForgetting(
        decay_factor=0.85,
        prune_threshold=0.05,
        stale_days=30,
    )

    while True:
        try:
            await asyncio.sleep(interval_hours * 3600)

            memories = await store.list_all(limit=1000)
            if not memories:
                LAST_SLEEP_REPORT.update(
                    {
                        "ran_at": utc_now().isoformat(),
                        "processed": 0,
                        "updated": 0,
                        "archived": 0,
                        "forgotten": 0,
                        "compressed": 0,
                        "consolidated": 0,
                    }
                )
                continue

            # 1. Standard Forgetting/Decay
            modified = forgetting.process_batch(memories)
            
            # 2. Deduplication (Merge highly similar memories)
            merged_count = await deduplicate_memories(store, memories)
            
            # 3. Abstraction (Turn Episode clusters into Knowledge)
            abstracted_count = await consolidate_episodes(store, memories)

            archived = 0
            forgotten = 0
            compressed = 0
            consolidated = 0

            for memory in modified:
                await store.update(memory)
                if memory.status.value == "archived":
                    archived += 1
                elif memory.status.value == "forgotten":
                    forgotten += 1
                elif memory.status.value == "compressed":
                    compressed += 1
                if memory.last_consolidated:
                    consolidated += 1

            LAST_SLEEP_REPORT.update(
                {
                    "ran_at": utc_now().isoformat(),
                    "processed": len(memories),
                    "updated": len(modified),
                    "archived": archived,
                    "forgotten": forgotten,
                    "compressed": compressed,
                    "consolidated": consolidated,
                    "merged": merged_count,
                    "abstracted": abstracted_count,
                }
            )

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
    """Placeholder for future LLM-driven abstraction of episodes into knowledge."""
    # In a real implementation, this would cluster episodes and call an LLM
    # to extract a 'Fact' or 'Semantic' memory from the cluster.
    return 0
