"""漸進式深度控制，用於記憶縮放級別。

此模組管理 L0/L1/L2 縮放級別，控制在檢索記憶時
包含多少細節。
"""

from ..models import MemoryNode, ZoomLevel


class MemoryZoom:
    """管理記憶檢索的漸進式深度級別。

    控制記憶在不同縮放級別時的呈現方式：
    - L0（摘要）：最高壓縮 - 僅概述
    - L1（摘要）：中等壓縮 - 關鍵點
    - L2（完整）：完整逐字內容
    """

    def __init__(self, default_level: ZoomLevel = ZoomLevel.L2_FULL):
        """初始化縮放控制器。

        Args:
            default_level: 檢索的默認縮放級別。
        """
        self.default_level = default_level
        self.current_level = default_level

    def set_level(self, level: ZoomLevel) -> None:
        """設定當前縮放級別。

        Args:
            level: 所需的縮放級別。
        """
        self.current_level = level

    def get_content(self, memory: MemoryNode) -> str:
        """在當前縮放級別獲取適當的內容。

        Args:
            memory: 要從中檢索內容的記憶。

        Returns:
            當前縮放級別的內容。
        """
        if self.current_level == ZoomLevel.L0_SUMMARY:
            return self._get_l0_content(memory)
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            return self._get_l1_content(memory)
        return memory.content

    def _get_l0_content(self, memory: MemoryNode) -> str:
        """獲取 L0（最高壓縮）內容。

        Args:
            memory: 要從中檢索內容的記憶。

        Returns:
            L0 摘要或回退到 L1/L2。
        """
        if memory.summary_l0:
            return memory.summary_l0
        elif memory.summary_l1:
            return memory.summary_l1
        return memory.content[:100] + "..." if len(memory.content) > 100 else memory.content

    def _get_l1_content(self, memory: MemoryNode) -> str:
        """獲取 L1（中等壓縮）內容。

        Args:
            memory: 要從中檢索內容的記憶。

        Returns:
            L1 摘要或回退到完整內容。
        """
        if memory.summary_l1:
            return memory.summary_l1
        return memory.content

    def zoom_in(self, memory: MemoryNode) -> str:
        """獲取更詳細的內容（放大）。

        Args:
            memory: 要從中檢索內容的記憶。

        Returns:
            下一個更詳細級別的內容。
        """
        if self.current_level == ZoomLevel.L0_SUMMARY:
            self.current_level = ZoomLevel.L1_ABSTRACT
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            self.current_level = ZoomLevel.L2_FULL
        return self.get_content(memory)

    def zoom_out(self, memory: MemoryNode) -> str:
        """獲取更壓縮的內容（縮小）。

        Args:
            memory: 要從中檢索內容的記憶。

        Returns:
            下一個更壓縮級別的內容。
        """
        if self.current_level == ZoomLevel.L2_FULL:
            self.current_level = ZoomLevel.L1_ABSTRACT
        elif self.current_level == ZoomLevel.L1_ABSTRACT:
            self.current_level = ZoomLevel.L0_SUMMARY
        return self.get_content(memory)

    def get_zoom_summary(self) -> dict[str, str]:
        """獲取每個縮放級別提供內容的摘要。

        Returns:
            描述每個縮放級別的字典。
        """
        return {
            "l0": "摘要 - 廣泛概述（最多 100 字符）",
            "l1": "摘要 - 關鍵點（最多 500 字符）",
            "l2": "完整 - 逐字內容（無限制）",
        }
