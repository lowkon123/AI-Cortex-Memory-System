"""LLM-driven hierarchical summarization for memory compression.

This module handles the generation of L0 and L1 summaries
that enable efficient memory retrieval at different zoom levels.
"""

from typing import Optional


class MemoryCompressor:
    """Hierarchical summarization for memory compression.

    Generates multi-level summaries to support zoom-based retrieval.
    Requires an external LLM API for actual summarization.
    """

    def __init__(self, llm_client: Optional[object] = None):
        """Initialize the compressor with an optional LLM client.

        Args:
            llm_client: External LLM API client for summarization.
        """
        self.llm_client = llm_client

    async def compress_to_l1(self, content: str) -> str:
        """Compress content to L1 abstract (key points).

        Args:
            content: The full memory content.

        Returns:
            L1 summary capturing key points.
        """
        if not self.llm_client:
            return self._fallback_l1(content)
        return await self._llm_summarize(content, max_tokens=500)

    async def compress_to_l0(self, content: str) -> str:
        """Compress content to L0 summary (broad overview).

        Args:
            content: The full memory content or L1 summary.

        Returns:
            L0 summary providing a broad overview.
        """
        if not self.llm_client:
            return self._fallback_l0(content)
        return await self._llm_summarize(content, max_tokens=100)

    def compress_batch(self, contents: list[str]) -> list[tuple[str, str]]:
        """Compress a batch of memories to both L0 and L1.

        Args:
            contents: List of memory contents.

        Returns:
            List of (l0_summary, l1_summary) tuples.
        """
        results = []
        for content in contents:
            l1 = self._fallback_l1(content) if not self.llm_client else None
            l0 = self._fallback_l0(content) if not self.llm_client else None
            results.append((l0 or "", l1 or ""))
        return results

    async def _llm_summarize(self, content: str, max_tokens: int) -> str:
        """Call external LLM for summarization.

        Args:
            content: Content to summarize.
            max_tokens: Maximum tokens in the summary.

        Returns:
            Generated summary text.
        """
        if not self.llm_client:
            raise RuntimeError("No LLM client configured")

        response = await self.llm_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"Summarize the following text in no more than {max_tokens} tokens. Focus on the most important points.",
                },
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _fallback_l1(self, content: str) -> str:
        """Simple fallback L1 summarization without LLM.

        Args:
            content: The full content.

        Returns:
            First 500 characters with ellipsis.
        """
        if len(content) <= 500:
            return content
        return content[:500] + "..."

    def _fallback_l0(self, content: str) -> str:
        """Simple fallback L0 summarization without LLM.

        Args:
            content: The full content.

        Returns:
            First 100 characters with ellipsis.
        """
        if len(content) <= 100:
            return content
        return content[:100] + "..."
