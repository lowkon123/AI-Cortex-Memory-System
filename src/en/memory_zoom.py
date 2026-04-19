"""Progressive depth control for memory zoom levels.

This module manages L0/L1/L2 zoom levels that control
how much detail is included when a memory is retrieved.
"""

from ..models import MemoryNode, ZoomLevel


class MemoryZoom:
    """Manages progressive depth levels for memory retrieval.

    Controls how memories are presented at different zoom levels:
    - L0 (summary): Most compressed - broad overview only
    - L1 (abstract): Medium compression - key points
    - L2 (full): Complete verbatim content
    """

    def __init__(self, default_level: ZoomLevel = ZoomLevel.L2_FULL):
        """Initialize the zoom controller.

        Args:
            default_level: Default zoom level for retrieval.
        """
        self.default_level = default_level
        self.current_level = default_level

    def set_level(self, level: ZoomLevel) -> None:
        """Set the current zoom level.

        Args:
            level: The desired zoom level.
        """
        self.current_level = level

    def get_content(self, memory: MemoryNode) -> str:
        """Get the appropriate content at the current zoom level.

        Args:
            memory: The memory to retrieve content from.

        Returns:
            The content at the current zoom level.
        """
        if self.current_level == ZoomLevel.L0_SUMMARY:
            return self._get_l0_content(memory)
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            return self._get_l1_content(memory)
        return memory.content

    def _get_l0_content(self, memory: MemoryNode) -> str:
        """Get L0 (most compressed) content.

        Args:
            memory: The memory to retrieve content from.

        Returns:
            L0 summary or fallback to L1/L2.
        """
        if memory.summary_l0:
            return memory.summary_l0
        elif memory.summary_l1:
            return memory.summary_l1
        return memory.content[:100] + "..." if len(memory.content) > 100 else memory.content

    def _get_l1_content(self, memory: MemoryNode) -> str:
        """Get L1 (medium compressed) content.

        Args:
            memory: The memory to retrieve content from.

        Returns:
            L1 abstract or fallback to full content.
        """
        if memory.summary_l1:
            return memory.summary_l1
        return memory.content

    def zoom_in(self, memory: MemoryNode) -> str:
        """Get more detailed content (zoom in).

        Args:
            memory: The memory to retrieve content from.

        Returns:
            Content at the next more detailed level.
        """
        if self.current_level == ZoomLevel.L0_SUMMARY:
            self.current_level = ZoomLevel.L1_ABSTRACT
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            self.current_level = ZoomLevel.L2_FULL
        return self.get_content(memory)

    def zoom_out(self, memory: MemoryNode) -> str:
        """Get more compressed content (zoom out).

        Args:
            memory: The memory to retrieve content from.

        Returns:
            Content at the next more compressed level.
        """
        if self.current_level == ZoomLevel.L2_FULL:
            self.current_level = ZoomLevel.L1_ABSTRACT
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            self.current_level = ZoomLevel.L0_SUMMARY
        return self.get_content(memory)

    def get_zoom_summary(self) -> dict[str, str]:
        """Get a summary of what each zoom level provides.

        Returns:
            Dictionary describing each zoom level.
        """
        return {
            "l0": "Summary - broad overview (100 chars max)",
            "l1": "Abstract - key points (500 chars max)",
            "l2": "Full - verbatim content (unlimited)",
        }
