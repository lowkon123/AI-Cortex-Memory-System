"""Token-aware context builder with progressive memory zoom."""

from __future__ import annotations

from enum import Enum
from typing import Optional

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None

from ..models import MemoryNode, ZoomLevel
from .memory_zoom import MemoryZoom


class InjectionPhase(str, Enum):
    """記憶注入的時序階段。

    修復問題 #49：過去注入點由呼叫方自行決定，缺乏明確語意。
    現在透過 InjectionPhase 明確標記要在哪個階段注入記憶。
    """

    PRE_CONTEXT = "pre_context"
    """對話前預填充：用於「背景知識」，注入在 System Prompt 最前面。"""

    MID_REASONING = "mid_reasoning"
    """推理中輔助：用於「當前問題相關事實」，注入在 System Prompt 末尾、User Message 之前。"""

    POST_RESPONSE = "post_response"
    """回應後更新：用於觸發記憶寫入，不影響當前回應。"""

    INLINE = "inline"
    """行內注入：直接嵌入 User Message，用於 Retrieval-Augmented 模式。"""


# 每個注入階段的 Token 預算佔比
PHASE_TOKEN_BUDGET_RATIO: dict[InjectionPhase, float] = {
    InjectionPhase.PRE_CONTEXT: 0.40,     # 最多用 40% 的 Token 做背景預填充
    InjectionPhase.MID_REASONING: 0.35,    # 最多用 35% 做即時記憶輔助
    InjectionPhase.POST_RESPONSE: 0.0,     # 不佔用 Token
    InjectionPhase.INLINE: 0.25,           # 行內嵌入最多 25%
}


class ContextBuilder:
    """Pack memories into context while staying inside a token budget."""

    def __init__(
        self,
        model: str = "gpt-4",
        max_tokens: int = 7000,
        encoding: Optional[str] = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self._encoding = encoding
        self._encoder = None
        self._zoom = MemoryZoom()

    def _get_encoder(self):
        if tiktoken is None:
            raise ImportError("tiktoken is required for token counting")
        if self._encoder is None:
            self._encoder = (
                tiktoken.get_encoding(self._encoding)
                if self._encoding
                else tiktoken.encoding_for_model(self.model)
            )
        return self._encoder

    def count_tokens(self, text: str) -> int:
        return len(self._get_encoder().encode(text))

    def build_context(
        self,
        memories: list[MemoryNode],
        system_prefix: str = "Relevant context from memory:",
        add_tokens: int = 0,
    ) -> str:
        ranked = [(memory, memory.activation_score or 0.5) for memory in memories]
        return self.build_context_with_zoom(
            ranked,
            system_prefix=system_prefix,
            add_tokens=add_tokens,
        )

    def build_context_with_zoom(
        self,
        memories: list[tuple[MemoryNode, float]],
        system_prefix: str = "Relevant context from memory:",
        add_tokens: int = 0,
    ) -> str:
        available_tokens = self.max_tokens - add_tokens
        available_tokens -= self.count_tokens(system_prefix) + 50

        context_parts: list[str] = []
        for memory, score in memories:
            content = self._get_zoomed_content(memory, score)
            header = self._format_header(memory, score)
            block = f"{header}\n{content}"
            token_count = self.count_tokens(block)

            if token_count <= available_tokens:
                context_parts.append(block)
                available_tokens -= token_count
                continue

            if available_tokens < 32:
                break

            truncated = self._truncate_to_tokens(block, available_tokens)
            context_parts.append(truncated)
            break

        if not context_parts:
            return system_prefix
        return f"{system_prefix}\n\n" + "\n\n---\n\n".join(context_parts)

    def _get_zoomed_content(self, memory: MemoryNode, score: float) -> str:
        if score >= 0.8:
            level = ZoomLevel.L2_FULL
        elif score >= 0.55:
            level = ZoomLevel.L1_ABSTRACT
        else:
            level = ZoomLevel.L0_SUMMARY

        self._zoom.set_level(level)
        content = self._zoom.get_content(memory)
        if content:
            return content
        return memory.summary_l0 or memory.summary_l1 or memory.content

    def _format_header(self, memory: MemoryNode, score: float) -> str:
        tags = ", ".join(memory.concept_tags[:4]) if memory.concept_tags else "no-tags"
        return (
            f"[score={score:.2f} kind={memory.memory_kind.value} "
            f"confidence={memory.confidence:.2f} tags={tags}]"
        )

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        encoder = self._get_encoder()
        tokens = encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return encoder.decode(tokens[:max_tokens]) + "..."

    def build_for_phase(
        self,
        memories: list[MemoryNode],
        phase: InjectionPhase,
        system_prefix: Optional[str] = None,
        add_tokens: int = 0,
    ) -> str:
        """根據注入時序階段建構記憶上下文。

        修復問題 #49：提供明確的 InjectionPhase 語意，
        呼叫方可精確控制記憶在哪個階段、以多少 Token 預算注入。

        Args:
            memories: 要注入的記憶節點列表。
            phase: 注入時序階段。
            system_prefix: 可選的自訂前綴文字。
            add_tokens: 已使用的 Token 數（用於計算剩餘預算）。

        Returns:
            適合該注入階段的格式化上下文字串。
        """
        if phase == InjectionPhase.POST_RESPONSE:
            # POST_RESPONSE 不直接生成文字，僅觸發記憶寫入
            return ""

        # 計算本階段的 Token 預算
        budget_ratio = PHASE_TOKEN_BUDGET_RATIO.get(phase, 0.35)
        phase_max_tokens = int(self.max_tokens * budget_ratio)
        remaining = phase_max_tokens - add_tokens

        if remaining <= 0:
            return ""

        # 選擇前綴文字
        phase_prefixes = {
            InjectionPhase.PRE_CONTEXT: "[背景記憶 | Background Context]",
            InjectionPhase.MID_REASONING: "[相關記憶 | Relevant Memory]",
            InjectionPhase.INLINE: "[記憶參考 | Memory Reference]",
        }
        prefix = system_prefix or phase_prefixes.get(phase, "Relevant context from memory:")

        # 暫時調整 Token 限制並建構內容
        original_max = self.max_tokens
        self.max_tokens = phase_max_tokens
        try:
            result = self.build_context(memories, system_prefix=prefix, add_tokens=add_tokens)
        finally:
            self.max_tokens = original_max

        return result

    def build_multi_phase(
        self,
        pre_memories: list[MemoryNode],
        mid_memories: list[MemoryNode],
    ) -> dict[InjectionPhase, str]:
        """一次建構多個注入階段的上下文。

        Args:
            pre_memories: 適合 PRE_CONTEXT 階段的背景記憶。
            mid_memories: 適合 MID_REASONING 階段的即時記憶。

        Returns:
            {InjectionPhase -> 格式化字串} 的字典。
        """
        return {
            InjectionPhase.PRE_CONTEXT: self.build_for_phase(
                pre_memories, InjectionPhase.PRE_CONTEXT
            ),
            InjectionPhase.MID_REASONING: self.build_for_phase(
                mid_memories, InjectionPhase.MID_REASONING
            ),
        }
