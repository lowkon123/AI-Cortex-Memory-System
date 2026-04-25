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
    """Timing phases for memory injection.

    Fixes #49: Injection points were previously arbitrary.
    Now InjectionPhase explicitly marks where to inject memories.
    """

    PRE_CONTEXT = "pre_context"
    """Pre-filling: Background knowledge injected at the start of System Prompt."""

    MID_REASONING = "mid_reasoning"
    """Reasoning aid: Task-related facts injected at the end of System Prompt."""

    POST_RESPONSE = "post_response"
    """Post-response update: Triggers memory writes, doesn't affect current response."""

    INLINE = "inline"
    """Inline injection: Embedded in User Message for Retrieval-Augmented mode."""


# Token budget ratios for each phase
PHASE_TOKEN_BUDGET_RATIO: dict[InjectionPhase, float] = {
    InjectionPhase.PRE_CONTEXT: 0.40,     # Up to 40% for background
    InjectionPhase.MID_REASONING: 0.35,    # Up to 35% for reasoning aid
    InjectionPhase.POST_RESPONSE: 0.0,     # No tokens
    InjectionPhase.INLINE: 0.25,           # Up to 25% for inline refs
}


class ContextBuilder:
    """Packs memories into context while staying inside a token budget."""

    def __init__(
        self,
        model: str = "gpt-4",
        max_tokens: int = 7000,
        encoding: Optional[str] = None,
    ):
        """Initialize ContextBuilder.

        Args:
            model: Model name for token counting.
            max_tokens: Maximum tokens allowed.
            encoding: Encoding name for tiktoken.
        """
        self.model = model
        self.max_tokens = max_tokens
        self._encoding = encoding
        self._encoder = None
        self._zoom = MemoryZoom()

    def _get_encoder(self):
        """Lazy loader for tiktoken encoder."""
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
        """Count tokens in a string."""
        return len(self._get_encoder().encode(text))

    def build_context(
        self,
        memories: list[MemoryNode],
        system_prefix: str = "Relevant context from memory:",
        add_tokens: int = 0,
    ) -> str:
        """Standard context building from memories."""
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
        """Build context using progressive zoom levels based on activation score."""
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
        """Select content based on zoom level derived from score."""
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
        """Format internal metadata header for a context block."""
        tags = ", ".join(memory.concept_tags[:4]) if memory.concept_tags else "no-tags"
        return (
            f"[score={score:.2f} kind={memory.memory_kind.value} "
            f"confidence={memory.confidence:.2f} tags={tags}]"
        )

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to stay within token budget."""
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
        """Build context for a specific timing phase.

        Fixes #49: Provides explicit InjectionPhase semantics.

        Args:
            memories: List of memories to inject.
            phase: Timing phase.
            system_prefix: Optional custom prefix.
            add_tokens: Already used tokens.

        Returns:
            Formatted context string for the phase.
        """
        if phase == InjectionPhase.POST_RESPONSE:
            return ""

        # Calculate token budget for this phase
        budget_ratio = PHASE_TOKEN_BUDGET_RATIO.get(phase, 0.35)
        phase_max_tokens = int(self.max_tokens * budget_ratio)
        remaining = phase_max_tokens - add_tokens

        if remaining <= 0:
            return ""

        # Select prefix text
        phase_prefixes = {
            InjectionPhase.PRE_CONTEXT: "[Background Context]",
            InjectionPhase.MID_REASONING: "[Relevant Memory]",
            InjectionPhase.INLINE: "[Memory Reference]",
        }
        prefix = system_prefix or phase_prefixes.get(phase, "Relevant context from memory:")

        # Temporarily adjust token limit
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
        """Build context for multiple injection phases at once."""
        return {
            InjectionPhase.PRE_CONTEXT: self.build_for_phase(
                pre_memories, InjectionPhase.PRE_CONTEXT
            ),
            InjectionPhase.MID_REASONING: self.build_for_phase(
                mid_memories, InjectionPhase.MID_REASONING
            ),
        }
