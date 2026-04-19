"""Sleep cycle management for background optimization and cold-data offloading.

This module implements the "Sleep Cycle" mechanism that manages
background tasks like compression, decay, and archival during idle periods.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional
from uuid import UUID


class SleepPhase(str, Enum):
    """Phases of the sleep cycle."""

    AWAKE = "awake"
    LIGHT_SLEEP = "light_sleep"
    DEEP_SLEEP = "deep_sleep"
    REM_SLEEP = "rem_sleep"


class MemoryScheduler:
    """Manages the sleep cycle for background memory optimization.

    Orchestrates maintenance tasks during appropriate sleep phases:
    - Light Sleep: Minor compression, freshness check
    - Deep Sleep: Major compression, archival, decay application
    - REM Sleep: Integration, cross-memory reinforcement
    """

    def __init__(
        self,
        on_light_sleep: Optional[Callable] = None,
        on_deep_sleep: Optional[Callable] = None,
        on_rem_sleep: Optional[Callable] = None,
    ):
        """Initialize the scheduler with optional phase handlers.

        Args:
            on_light_sleep: Handler for light sleep tasks.
            on_deep_sleep: Handler for deep sleep tasks.
            on_rem_sleep: Handler for REM sleep tasks.
        """
        self.on_light_sleep = on_light_sleep
        self.on_deep_sleep = on_deep_sleep
        self.on_rem_sleep = on_rem_sleep
        self._current_phase = SleepPhase.AWAKE
        self._is_running = False
        self._last_light_sleep = datetime.utcnow()
        self._last_deep_sleep = datetime.utcnow() - timedelta(hours=1)
        self._last_rem_sleep = datetime.utcnow() - timedelta(hours=2)

    @property
    def current_phase(self) -> SleepPhase:
        """Get the current sleep phase."""
        return self._current_phase

    @property
    def is_sleeping(self) -> bool:
        """Check if the scheduler is in any sleep phase."""
        return self._current_phase != SleepPhase.AWAKE

    def should_enter_light_sleep(self, idle_minutes: int = 5) -> bool:
        """Check if conditions for light sleep are met.

        Args:
            idle_minutes: Minutes of inactivity before light sleep.

        Returns:
            True if light sleep should begin.
        """
        if self._current_phase != SleepPhase.AWAKE:
            return False
        elapsed = datetime.utcnow() - self._last_light_sleep
        return elapsed.total_seconds() >= idle_minutes * 60

    def should_enter_deep_sleep(self, idle_minutes: int = 30) -> bool:
        """Check if conditions for deep sleep are met.

        Args:
            idle_minutes: Minutes of inactivity before deep sleep.

        Returns:
            True if deep sleep should begin.
        """
        if self._current_phase != SleepPhase.LIGHT_SLEEP:
            return False
        elapsed = datetime.utcnow() - self._last_deep_sleep
        return elapsed.total_seconds() >= idle_minutes * 60

    async def enter_light_sleep(self) -> None:
        """Transition to light sleep phase."""
        self._current_phase = SleepPhase.LIGHT_SLEEP
        if self.on_light_sleep:
            await self.on_light_sleep()
        self._last_light_sleep = datetime.utcnow()

    async def enter_deep_sleep(self) -> None:
        """Transition to deep sleep phase."""
        self._current_phase = SleepPhase.DEEP_SLEEP
        if self.on_deep_sleep:
            await self.on_deep_sleep()
        self._last_deep_sleep = datetime.utcnow()

    async def enter_rem_sleep(self) -> None:
        """Transition to REM sleep phase."""
        self._current_phase = SleepPhase.REM_SLEEP
        if self.on_rem_sleep:
            await self.on_rem_sleep()
        self._last_rem_sleep = datetime.utcnow()

    async def wake(self) -> None:
        """Transition back to awake state."""
        self._current_phase = SleepPhase.AWAKE

    async def sleep_cycle(self, idle_minutes_light: int = 5, idle_minutes_deep: int = 30) -> None:
        """Run a complete sleep cycle, transitioning through phases.

        Args:
            idle_minutes_light: Idle minutes before light sleep.
            idle_minutes_deep: Idle minutes before deep sleep.
        """
        if self.should_enter_light_sleep(idle_minutes_light):
            await self.enter_light_sleep()
            await asyncio.sleep(2)

        if self.should_enter_deep_sleep(idle_minutes_deep):
            await self.enter_deep_sleep()
            await asyncio.sleep(3)

        if self._current_phase in (SleepPhase.LIGHT_SLEEP, SleepPhase.DEEP_SLEEP):
            await self.enter_rem_sleep()
            await asyncio.sleep(1)

        await self.wake()

    def get_status(self) -> dict:
        """Get the current scheduler status.

        Returns:
            Dictionary with phase and timing information.
        """
        return {
            "phase": self._current_phase.value,
            "is_sleeping": self.is_sleeping,
            "last_light_sleep": self._last_light_sleep.isoformat(),
            "last_deep_sleep": self._last_deep_sleep.isoformat(),
            "last_rem_sleep": self._last_rem_sleep.isoformat(),
        }

    async def offload_cold_data(
        self,
        memory_ids: list[UUID],
        offloader: Callable[[list[UUID]], None],
    ) -> None:
        """Offload cold (infrequently accessed) memories to cold storage.

        Args:
            memory_ids: List of memory IDs to offload.
            offloader: Function to handle the actual offloading.
        """
        if self._current_phase == SleepPhase.DEEP_SLEEP:
            offloader(memory_ids)
