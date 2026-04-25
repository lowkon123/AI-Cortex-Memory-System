"""Progressive depth control for memory zoom levels.

This module manages L0/L1/L2 zoom levels, controlling how much 
detail is included when retrieving a memory.
"""

from ..models import MemoryNode, ZoomLevel


class MemoryZoom:
    """Manages progressive depth levels for memory retrieval.

    Controls how memories are presented at different zoom levels:
    - L0 (Summary): Highest compression - Overview only.
    - L1 (Abstract): Medium compression - Key points.
    - L2 (Full): Full verbatim content.
    """

    def __init__(self, default_level: ZoomLevel = ZoomLevel.L2_FULL):
        """Initialize zoom controller.

        Args:
            default_level: Default zoom level for retrieval.
        """
        self.default_level = default_level
        self.current_level = default_level

    def set_level(self, level: ZoomLevel) -> None:
        """Set the current zoom level.

        Args:
            level: Desired zoom level.
        """
        self.current_level = level

    def zoom(self, memory: MemoryNode, level: ZoomLevel) -> str:
        """Alias for set_level + get_content.

        Args:
            memory: Memory to retrieve content from.
            level: Desired zoom level.

        Returns:
            Content at the specified zoom level.
        """
        self.set_level(level)
        return self.get_content(memory)

    def get_content(self, memory: MemoryNode) -> str:
        """Get the appropriate content at the current zoom level.

        Args:
            memory: Memory to retrieve content from.

        Returns:
            Content at the current zoom level.
        """
        if self.current_level == ZoomLevel.L0_SUMMARY:
            return self._get_l0_content(memory)
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            return self._get_l1_content(memory)
        return memory.content

    def _get_l0_content(self, memory: MemoryNode) -> str:
        """Retrieve L0 (highest compression) content.

        Args:
            memory: Memory to retrieve content from.

        Returns:
            L0 summary or fallbacks.
        """
        if memory.summary_l0:
            return memory.summary_l0
        elif memory.summary_l1:
            return memory.summary_l1
        return memory.content[:100] + "..." if len(memory.content) > 100 else memory.content

    def _get_l1_content(self, memory: MemoryNode) -> str:
        """Retrieve L1 (medium compression) content.

        Args:
            memory: Memory to retrieve content from.

        Returns:
            L1 summary or fallback to full content.
        """
        if memory.summary_l1:
            return memory.summary_l1
        return memory.content

    def zoom_in(self, memory: MemoryNode) -> str:
        """Step down to a more detailed level (zoom in).

        Args:
            memory: Memory to retrieve content from.

        Returns:
            Content at the next more detailed level.
        """
        if self.current_level == ZoomLevel.L0_SUMMARY:
            self.current_level = ZoomLevel.L1_ABSTRACT
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            self.current_level = ZoomLevel.L2_FULL
        return self.get_content(memory)

    def zoom_out(self, memory: MemoryNode) -> str:
        """Step up to a more compressed level (zoom out).

        Args:
            memory: Memory to retrieve content from.

        Returns:
            Content at the next more compressed level.
        """
        if self.current_level == ZoomLevel.L2_FULL:
            self.current_level = ZoomLevel.L1_ABSTRACT
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            self.current_level = ZoomLevel.L0_SUMMARY
        return self.get_content(memory)

    def get_zoom_summary(self) -> dict[str, str]:
        """Get description of what each zoom level provides.

        Returns:
            A dictionary describing each zoom level.
        """
        return {
            "l0": "Summary - Broad overview (max 100 chars)",
            "l1": "Abstract - Key points (max 500 chars)",
            "l2": "Full - Verbatim content (unlimited)",
        }
