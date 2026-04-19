"""FAISS 向量搜索集成，用於語義記憶檢索。

此模組使用 FAISS 提供基於向量的相似性搜索，
實現超越關鍵字匹配的語義記憶召回。
"""

import faiss
import numpy as np
from typing import Optional

from ..models import MemoryNode, MemoryStoreConfig


class MemoryVectorStore:
    """基於 FAISS 的語義記憶搜索向量存儲。

    提供高效的最近鄰搜索以檢索記憶。
    """

    def __init__(self, config: MemoryStoreConfig):
        """使用配置初始化向量存儲。

        Args:
            config: 具有向量維度的記憶存儲配置。
        """
        self.config = config
        self.index: Optional[faiss.Index] = None
        self._id_to_idx: dict[str, int] = {}
        self._idx_to_id: dict[int, str] = {}

    def init_index(self, dim: Optional[int] = None) -> None:
        """初始化新的 FAISS 索引。

        Args:
            dim: 向量維度。默認為配置值。
        """
        dim = dim or self.config.vector_dim
        self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))
        self._id_to_idx = {}
        self._idx_to_id = {}

    def add_memory(self, memory: MemoryNode) -> None:
        """將記憶的嵌入向量添加到索引。

        Args:
            memory: 具有嵌入向量的大腦節點。

        Raises:
            ValueError: 如果記憶沒有嵌入向量。
        """
        if memory.embedding is None:
            raise ValueError(f"Memory {memory.id} has no embedding")

        vector = np.array(memory.embedding, dtype=np.float32)
        if vector.ndim == 1:
            vector = vector.reshape(1, -1)

        idx = len(self._id_to_idx)
        self._id_to_idx[str(memory.id)] = idx
        self._idx_to_id[idx] = str(memory.id)

        idx_arr = np.array([idx], dtype=np.int64)
        self.index.add_with_ids(vector, idx_arr)

    def remove_memory(self, memory_id: str) -> None:
        """從索引中移除記憶。

        Args:
            memory_id: 要移除的記憶的 ID。

        Note:
            FAISS 不支持直接移除；這是一個無操作佔位符。
        """
        pass

    def search(
        self, query_vector: list[float], k: int = 5
    ) -> list[tuple[str, float]]:
        """搜索查詢向量最近的 k 個記憶。

        Args:
            query_vector: 查詢嵌入向量。
            k: 要返回的鄰居數量。

        Returns:
            按距離排序的 (memory_id, 距離) 元組列表。
        """
        if self.index is None:
            return []

        vector = np.array(query_vector, dtype=np.float32)
        if vector.ndim == 1:
            vector = vector.reshape(1, -1)

        distances, indices = self.index.search(vector, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx in self._idx_to_id:
                results.append((self._idx_to_id[idx], float(dist)))

        return results

    def search_by_memory(
        self, memory: MemoryNode, k: int = 5
    ) -> list[tuple[str, float]]:
        """使用另一個記憶的嵌入向量作為查詢進行搜索。

        Args:
            memory: 其嵌入向量用作查詢的記憶。
            k: 要返回的鄰居數量。

        Returns:
            (memory_id, 距離) 元組列表。
        """
        if memory.embedding is None:
            return []
        return self.search(memory.embedding, k)

    def save_index(self, path: str) -> None:
        """將索引保存到磁盤。

        Args:
            path: 索引文件的路徑。
        """
        if self.index is not None:
            faiss.write_index(self.index, path)

    def load_index(self, path: str) -> None:
        """從磁盤加載索引。

        Args:
            path: 索引文件的路徑。
        """
        self.index = faiss.read_index(path)
