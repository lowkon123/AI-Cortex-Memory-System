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

            modified = forgetting.process_batch(memories)
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
                }
            )

        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)


def get_last_sleep_report() -> dict:
    """Return the most recent background maintenance summary."""
    return LAST_SLEEP_REPORT.copy()
