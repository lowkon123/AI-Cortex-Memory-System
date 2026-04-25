"""Resource Manager — Async resource isolation layer.

Fixes #45: Memory queries (Memory I/O) and LLM inference sharing 
resources, leading to competition under high load and slowing down 
the entire response.

This module uses asyncio Semaphores to isolate the concurrency of 
both resource types:
- Memory I/O Semaphore: Limit concurrent memory queries.
- LLM Semaphore: Ensure LLM inference gets priority for compute resources.

Priority: LLM Inference > Memory I/O > Background Maintenance
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, Optional, TypeVar

T = TypeVar("T")


class PriorityLevel:
    """Resource priority constants."""
    LLM = "llm"                  # Highest: LLM Inference
    MEMORY_READ = "memory_read"  # Mid: Memory lookup (Read)
    MEMORY_WRITE = "memory_write" # Low: Memory write
    MAINTENANCE = "maintenance"  # Lowest: Background maintenance


class ResourceManager:
    """Async manager isolating Memory I/O and LLM Inference resources.

    Usage:
        manager = ResourceManager()

        # Restricted memory lookup (doesn't block LLM)
        result = await manager.memory_lookup(store.hybrid_search, query, vec)

        # LLM priority channel
        result = await manager.llm_call(ollama_client.generate, prompt)
    """

    def __init__(
        self,
        max_concurrent_memory_reads: int = 5,
        max_concurrent_memory_writes: int = 2,
        max_concurrent_llm: int = 3,
        max_concurrent_maintenance: int = 1,
        timeout_memory: float = 10.0,
        timeout_llm: float = 120.0,
    ):
        """Initialize Resource Manager.

        Args:
            max_concurrent_memory_reads: Max concurrent memory lookups.
            max_concurrent_memory_writes: Max concurrent memory writes.
            max_concurrent_llm: Max concurrent LLM requests (Ollama usually supports 1–3).
            max_concurrent_maintenance: Max concurrent maintenance tasks.
            timeout_memory: Timeout for memory queries (seconds).
            timeout_llm: Timeout for LLM calls (seconds).
        """
        self._memory_read_sem = asyncio.Semaphore(max_concurrent_memory_reads)
        self._memory_write_sem = asyncio.Semaphore(max_concurrent_memory_writes)
        self._llm_sem = asyncio.Semaphore(max_concurrent_llm)
        self._maintenance_sem = asyncio.Semaphore(max_concurrent_maintenance)

        self._timeout_memory = timeout_memory
        self._timeout_llm = timeout_llm

        # Statistics
        self._stats: dict[str, int] = {
            "memory_reads": 0,
            "memory_writes": 0,
            "llm_calls": 0,
            "maintenance_tasks": 0,
            "timeouts": 0,
            "errors": 0,
        }
        self._latencies: dict[str, list[float]] = {
            "memory_read": [],
            "memory_write": [],
            "llm": [],
        }

    async def memory_lookup(
        self,
        fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        fallback: Any = None,
        **kwargs: Any,
    ) -> T:
        """Run a memory lookup (read) through the restricted semaphore.

        Args:
            fn: Async lookup function.
            *args: Positional arguments for fn.
            fallback: Value to return on timeout or error.
            **kwargs: Keyword arguments for fn.

        Returns:
            Function result or fallback on timeout/error.
        """
        start = time.monotonic()
        try:
            async with asyncio.timeout(self._timeout_memory):
                async with self._memory_read_sem:
                    result = await fn(*args, **kwargs)
                    self._stats["memory_reads"] += 1
                    self._record_latency("memory_read", time.monotonic() - start)
                    return result
        except TimeoutError:
            self._stats["timeouts"] += 1
            return fallback
        except Exception:
            self._stats["errors"] += 1
            return fallback

    async def memory_write(
        self,
        fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[T]:
        """Run a memory write through the restricted semaphore."""
        start = time.monotonic()
        try:
            async with asyncio.timeout(self._timeout_memory * 2):
                async with self._memory_write_sem:
                    result = await fn(*args, **kwargs)
                    self._stats["memory_writes"] += 1
                    self._record_latency("memory_write", time.monotonic() - start)
                    return result
        except Exception:
            self._stats["errors"] += 1
            return None

    async def llm_call(
        self,
        fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[T]:
        """Run an LLM inference request through the priority channel.

        LLM calls have an independent semaphore and longer timeouts, 
        ensuring they don't compete with I/O.
        """
        start = time.monotonic()
        try:
            async with asyncio.timeout(self._timeout_llm):
                async with self._llm_sem:
                    result = await fn(*args, **kwargs)
                    self._stats["llm_calls"] += 1
                    self._record_latency("llm", time.monotonic() - start)
                    return result
        except TimeoutError:
            self._stats["timeouts"] += 1
            return None
        except Exception:
            self._stats["errors"] += 1
            return None

    async def maintenance_task(
        self,
        fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[T]:
        """Run a maintenance task (lowest priority)."""
        try:
            async with self._maintenance_sem:
                result = await fn(*args, **kwargs)
                self._stats["maintenance_tasks"] += 1
                return result
        except Exception:
            self._stats["errors"] += 1
            return None

    def _record_latency(self, category: str, latency: float) -> None:
        """Record latency stats (last 100 entries)."""
        history = self._latencies.get(category, [])
        history.append(latency)
        if len(history) > 100:
            history.pop(0)
        self._latencies[category] = history

    def get_stats(self) -> dict:
        """Fetch resource usage statistics report."""
        avg_latencies = {
            category: (sum(vals) / len(vals) if vals else 0.0)
            for category, vals in self._latencies.items()
        }
        return {
            **self._stats,
            "avg_latencies_ms": {
                k: round(v * 1000, 2) for k, v in avg_latencies.items()
            },
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        for key in self._stats:
            self._stats[key] = 0
        for key in self._latencies:
            self._latencies[key] = []


# Module-level default instance
_default_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Fetch default ResourceManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ResourceManager()
    return _default_manager
