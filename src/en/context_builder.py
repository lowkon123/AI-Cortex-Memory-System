"""Token-efficient context injection for LLM prompts.

This module builds context strings from memories, managing
token budgets to fit within LLM context windows.
"""

from typing import Optional

try:
    import tiktoken
except ImportError:
    tiktoken = None

from ..models import MemoryNode


class ContextBuilder:
    """Builds token-efficient context strings from memory nodes.

    Manages token budgets and formats memories for LLM injection.
    """

    def __init__(
        self,
        model: str = "gpt-4",
        max_tokens: int = 7000,
        encoding: Optional[str] = None,
    ):
        """Initialize the context builder.

        Args:
            model: The LLM model for token counting.
            max_tokens: Maximum tokens to use for context.
            encoding: Optional tiktoken encoding name.
        """
        self.model = model
        self.max_tokens = max_tokens
        self._encoding = encoding
        self._encoder = None

    def _get_encoder(self):
        """Get or create the tiktoken encoder.

        Returns:
            Tiktoken encoder instance.
        """
        if tiktoken is None:
            raise ImportError("tiktoken is required for token counting")

        if self._encoder is None:
            self._encoder = tiktoken.encoding_for_model(self.model)
        return self._encoder

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string.

        Args:
            text: The text to count.

        Returns:
            Number of tokens.
        """
        encoder = self._get_encoder()
        return len(encoder.encode(text))

    def build_context(
        self,
        memories: list[MemoryNode],
        system_prefix: str = "Relevant context from memory:",
        add_tokens: int = 0,
    ) -> str:
        """Build a context string from a list of memories.

        Args:
            memories: List of memory nodes to include.
            system_prefix: Prefix to add before the context.
            add_tokens: Additional tokens to reserve.

        Returns:
            Formatted context string.
        """
        available_tokens = self.max_tokens - add_tokens
        available_tokens -= self.count_tokens(system_prefix) + 50

        context_parts = []
        for memory in memories:
            content = memory.content
            token_count = self.count_tokens(content)

            if token_count <= available_tokens:
                context_parts.append(content)
                available_tokens -= token_count
            else:
                truncated = self._truncate_to_tokens(content, available_tokens - 10)
                context_parts.append(truncated)
                break

        if not context_parts:
            return system_prefix

        return f"{system_prefix}\n\n" + "\n\n---\n\n".join(context_parts)

    def build_context_with_zoom(
        self,
        memories: list[tuple[MemoryNode, int]],
        system_prefix: str = "Relevant context from memory:",
    ) -> str:
        """Build context using per-memory zoom levels.

        Args:
            memories: List of (memory, score) tuples.
            system_prefix: Prefix to add before the context.

        Returns:
            Formatted context string with zoom-appropriate content.
        """
        from .memory_zoom import MemoryZoom

        zoom = MemoryZoom()
        context_parts = []
        available_tokens = self.max_tokens - 100

        for memory, score in memories:
            if score < 0.3:
                zoom.set_level(memory.zoom_level)
            elif score < 0.6:
                zoom.set_level(memory.zoom_level)
            else:
                zoom.set_level(memory.zoom_level)

            content = zoom.get_content(memory)
            token_count = self.count_tokens(content)

            if token_count <= available_tokens:
                context_parts.append(f"[relevance: {score:.2f}] {content}")
                available_tokens -= token_count
            else:
                break

        if not context_parts:
            return system_prefix

        return f"{system_prefix}\n\n" + "\n\n---\n\n".join(context_parts)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token budget.

        Args:
            text: The text to truncate.
            max_tokens: Maximum tokens allowed.

        Returns:
            Truncated text.
        """
        encoder = self._get_encoder()
        tokens = encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return encoder.decode(tokens[:max_tokens]) + "..."
