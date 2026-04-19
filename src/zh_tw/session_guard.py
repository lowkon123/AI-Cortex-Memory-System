"""Session Guard — Debug/Test Session 隔離層。

修復問題 #9：測試輸入（Debug Prompt）不會污染正式記憶庫。

所有透過 test=True 旗標存入的記憶，會被路由到獨立的
'__test__' Persona Namespace，絕對不會影響正式的 AI 決策。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from ..models import MemoryNode, MemoryStatus

# 測試用的保留 Persona 名稱
TEST_PERSONA_PREFIX = "__test__"
DEBUG_PERSONA_PREFIX = "__debug__"


class SessionGuard:
    """隔離測試與正式記憶的守衛層。

    使用方式：
        guard = SessionGuard()
        node = MemoryNode(content="測試內容", ...)
        safe_node = guard.sandbox(node)      # 標記為測試，不影響正式庫
        guard.is_test(safe_node)             # True
    """

    def __init__(self, test_persona: str = TEST_PERSONA_PREFIX):
        self._test_persona = test_persona
        self._active_test_sessions: set[UUID] = set()

    def sandbox(
        self,
        node: MemoryNode,
        session_id: Optional[UUID] = None,
        reason: str = "test",
    ) -> MemoryNode:
        """將記憶節點標記為沙盒模式（不污染正式庫）。

        Args:
            node: 要隔離的記憶節點。
            session_id: 可選的 Session ID，用於批次隔離。
            reason: 隔離原因（'test' | 'debug' | 'dry_run'）。

        Returns:
            被路由到測試 Namespace 的記憶節點（就地修改）。
        """
        prefix = DEBUG_PERSONA_PREFIX if reason == "debug" else TEST_PERSONA_PREFIX
        # 保留原始 persona，但前綴化
        original_persona = node.persona or "default"
        node.persona = f"{prefix}{original_persona}"
        node.metadata["_sandboxed"] = True
        node.metadata["_sandbox_reason"] = reason

        if session_id:
            self._active_test_sessions.add(session_id)

        return node

    def is_test(self, node: MemoryNode) -> bool:
        """檢查記憶節點是否為測試 Sandbox 記憶。"""
        return node.persona.startswith(TEST_PERSONA_PREFIX) or node.persona.startswith(
            DEBUG_PERSONA_PREFIX
        )

    def is_production(self, node: MemoryNode) -> bool:
        """檢查記憶節點是否為正式記憶（非沙盒）。"""
        return not self.is_test(node)

    def mark_test_session(self, session_id: UUID) -> None:
        """將整個 Session 標記為測試 Session。"""
        self._active_test_sessions.add(session_id)

    def is_test_session(self, session_id: Optional[UUID]) -> bool:
        """檢查 Session ID 是否為測試 Session。"""
        if not session_id:
            return False
        return session_id in self._active_test_sessions

    def clear_test_session(self, session_id: UUID) -> None:
        """清除測試 Session 標記。"""
        self._active_test_sessions.discard(session_id)

    def filter_production(self, nodes: list[MemoryNode]) -> list[MemoryNode]:
        """從列表中過濾出純正式記憶（排除所有沙盒記憶）。"""
        return [n for n in nodes if self.is_production(n)]

    def filter_sandbox(self, nodes: list[MemoryNode]) -> list[MemoryNode]:
        """從列表中過濾出所有沙盒記憶。"""
        return [n for n in nodes if self.is_test(n)]

    @asynccontextmanager
    async def test_context(self, store, session_id: Optional[UUID] = None):
        """非同步上下文管理器：自動在結束後清理沙盒記憶。

        Usage:
            async with guard.test_context(store, session_id=my_session) as g:
                node = g.sandbox(my_node)
                await store.insert(node)
            # 退出後：沙盒記憶被自動 FORGOTTEN
        """
        if session_id:
            self.mark_test_session(session_id)
        try:
            yield self
        finally:
            # 自動將該 Session 的沙盒記憶標記為 FORGOTTEN
            if session_id:
                all_nodes = await store.list_by_session(session_id)
                for node in all_nodes:
                    if self.is_test(node):
                        node.status = MemoryStatus.FORGOTTEN
                        await store.update(node)
                self.clear_test_session(session_id)


# 模組級別的預設實例（Singleton Pattern）
_default_guard: Optional[SessionGuard] = None


def get_guard() -> SessionGuard:
    """取得模組預設的 SessionGuard 實例。"""
    global _default_guard
    if _default_guard is None:
        _default_guard = SessionGuard()
    return _default_guard
