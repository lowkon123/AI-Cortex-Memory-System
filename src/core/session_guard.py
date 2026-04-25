"""Session Guard — Debug/Test session isolation layer.

Fixes #9: Ensures test inputs (Debug Prompts) do not contaminate 
the production memory pool.

All memories stored with a test flag are routed to independent 
'__test__' or '__debug__' Persona Namespaces, ensuring they never 
impact production AI decisions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from ..models import MemoryNode, MemoryStatus

# Reserved Persona prefixes for testing
TEST_PERSONA_PREFIX = "__test__"
DEBUG_PERSONA_PREFIX = "__debug__"


class SessionGuard:
    """Guard layer isolating test and production memories.

    Usage:
        guard = SessionGuard()
        node = MemoryNode(content="test content", ...)
        safe_node = guard.sandbox(node)      # Labeled as test
        guard.is_test(safe_node)             # True
    """

    def __init__(self, test_persona: str = TEST_PERSONA_PREFIX):
        """Initialize SessionGuard."""
        self._test_persona = test_persona
        self._active_test_sessions: set[UUID] = set()

    def sandbox(
        self,
        node: MemoryNode,
        session_id: Optional[UUID] = None,
        reason: str = "test",
    ) -> MemoryNode:
        """Mark a memory node for sandbox mode (isolated from production).

        Args:
            node: Memory node to isolate.
            session_id: Optional Session ID for batch isolation.
            reason: Isolation reason ('test' | 'debug' | 'dry_run').

        Returns:
            Isolated memory node routed to test namespace (modified in-place).
        """
        prefix = DEBUG_PERSONA_PREFIX if reason == "debug" else TEST_PERSONA_PREFIX
        # Preserve original persona but prefix it
        original_persona = node.persona or "default"
        node.persona = f"{prefix}{original_persona}"
        node.metadata["_sandboxed"] = True
        node.metadata["_sandbox_reason"] = reason

        if session_id:
            self._active_test_sessions.add(session_id)

        return node

    def is_test(self, node: MemoryNode) -> bool:
        """Check if a memory node is a test/sandbox memory."""
        return node.persona.startswith(TEST_PERSONA_PREFIX) or node.persona.startswith(
            DEBUG_PERSONA_PREFIX
        )

    def is_production(self, node: MemoryNode) -> bool:
        """Check if a memory node is production (not sandboxed)."""
        return not self.is_test(node)

    def mark_test_session(self, session_id: UUID) -> None:
        """Mark an entire session as a test session."""
        self._active_test_sessions.add(session_id)

    def is_test_session(self, session_id: Optional[UUID]) -> bool:
        """Check if a session ID is a test session."""
        if not session_id:
            return False
        return session_id in self._active_test_sessions

    def clear_test_session(self, session_id: UUID) -> None:
        """Clear test session marker."""
        self._active_test_sessions.discard(session_id)

    def filter_production(self, nodes: list[MemoryNode]) -> list[MemoryNode]:
        """Filter production-only memories from a list (excl. sandboxed)."""
        return [n for n in nodes if self.is_production(n)]

    def filter_sandbox(self, nodes: list[MemoryNode]) -> list[MemoryNode]:
        """Filter sandbox-only memories from a list."""
        return [n for n in nodes if self.is_test(n)]

    @asynccontextmanager
    async def test_context(self, store, session_id: Optional[UUID] = None):
        """Async context manager for sandbox testing.

        Usage:
            async with guard.test_context(store, session_id=my_session) as g:
                node = g.sandbox(my_node)
                await store.insert(node)
            # Exit: Sandbox memories are automatically marked as FORGOTTEN.
        """
        if session_id:
            self.mark_test_session(session_id)
        try:
            yield self
        finally:
            # Mark sandbox memories from this session as FORGOTTEN
            if session_id:
                all_nodes = await store.list_by_session(session_id)
                for node in all_nodes:
                    if self.is_test(node):
                        node.status = MemoryStatus.FORGOTTEN
                        await store.update(node)
                self.clear_test_session(session_id)


# Module-level default instance (Singleton Pattern)
_default_guard: Optional[SessionGuard] = None


def get_guard() -> SessionGuard:
    """Fetch default SessionGuard instance."""
    global _default_guard
    if _default_guard is None:
        _default_guard = SessionGuard()
    return _default_guard
