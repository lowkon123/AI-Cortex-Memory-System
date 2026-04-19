"""Token-aware context builder with progressive memory zoom."""

from __future__ import annotations

from typing import Optional

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None

from ..models import MemoryNode, ZoomLevel
from .memory_zoom import MemoryZoom


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
