"""Resource Manager — Async 資源隔離層。

修復問題 #45：記憶查詢（Memory I/O）與 LLM 推理共用資源，
導致高負載時兩者相互競爭，拖慢整體回應速度。

此模組使用 asyncio Semaphore 隔離兩種資源的並發量：
- Memory I/O Semaphore：限制同時進行的記憶查詢數
- LLM Semaphore：確保 LLM 推理優先獲得計算資源

優先級：LLM 推理 > Memory I/O > Background Maintenance
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, Optional, TypeVar

T = TypeVar("T")


class PriorityLevel:
    """資源優先級常數。"""
    LLM = "llm"                  # 最高：LLM 推理
    MEMORY_READ = "memory_read"  # 中：記憶查詢（讀）
    MEMORY_WRITE = "memory_write" # 低：記憶寫入
    MAINTENANCE = "maintenance"  # 最低：背景維護


class ResourceManager:
    """隔離 Memory I/O 與 LLM 推理資源的非同步管理器。

    使用方式：
        manager = ResourceManager()

        # 受限的記憶查詢（不阻塞 LLM）
        result = await manager.memory_lookup(store.hybrid_search, query, vec)

        # LLM 優先通道
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
        """初始化資源管理器。

        Args:
            max_concurrent_memory_reads: 最大並發記憶讀取數。
            max_concurrent_memory_writes: 最大並發記憶寫入數。
            max_concurrent_llm: 最大並發 LLM 請求數（Ollama 通常支援 1–3）。
            max_concurrent_maintenance: 最大並發維護任務數。
            timeout_memory: 記憶查詢超時（秒）。
            timeout_llm: LLM 呼叫超時（秒）。
        """
        self._memory_read_sem = asyncio.Semaphore(max_concurrent_memory_reads)
        self._memory_write_sem = asyncio.Semaphore(max_concurrent_memory_writes)
        self._llm_sem = asyncio.Semaphore(max_concurrent_llm)
        self._maintenance_sem = asyncio.Semaphore(max_concurrent_maintenance)

        self._timeout_memory = timeout_memory
        self._timeout_llm = timeout_llm

        # 統計
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
        """透過受限 Semaphore 執行記憶查詢（讀）。

        Args:
            fn: 非同步記憶查詢函數。
            *args: 函數參數。
            fallback: 超時或錯誤時的回退值。
            **kwargs: 函數關鍵字參數。

        Returns:
            函數結果，或在超時/錯誤時返回 fallback。
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
        """透過受限 Semaphore 執行記憶寫入。"""
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
        """透過優先通道執行 LLM 推理請求。

        LLM 呼叫擁有獨立的 Semaphore，不與 Memory I/O 競爭，
        且擁有更長的超時容限。
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
        """執行背景維護任務（最低優先級）。"""
        try:
            async with self._maintenance_sem:
                result = await fn(*args, **kwargs)
                self._stats["maintenance_tasks"] += 1
                return result
        except Exception:
            self._stats["errors"] += 1
            return None

    def _record_latency(self, category: str, latency: float) -> None:
        """記錄延遲統計（保留最近 100 筆）。"""
        history = self._latencies.get(category, [])
        history.append(latency)
        if len(history) > 100:
            history.pop(0)
        self._latencies[category] = history

    def get_stats(self) -> dict:
        """取得資源使用統計報告。"""
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
        """重置統計數據。"""
        for key in self._stats:
            self._stats[key] = 0
        for key in self._latencies:
            self._latencies[key] = []


# 模組級別預設實例
_default_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """取得模組預設的 ResourceManager 實例。"""
    global _default_manager
    if _default_manager is None:
        _default_manager = ResourceManager()
    return _default_manager
