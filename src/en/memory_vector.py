"""FAISS vector search integration for semantic memory retrieval.

This module provides vector-based similarity search using FAISS,
enabling semantic recall of memories beyond keyword matching.
"""

import faiss
import numpy as np
from typing import Optional

from ..models import MemoryNode, MemoryStoreConfig


class MemoryVectorStore:
    """FAISS-based vector store for semantic memory search.

    Provides efficient nearest-neighbor search for memory retrieval.
    """

    def __init__(self, config: MemoryStoreConfig):
        """Initialize the vector store with configuration.

        Args:
            config: Memory store configuration with vector dimensions.
        """
        self.config = config
        self.index: Optional[faiss.Index] = None
        self._id_to_idx: dict[str, int] = {}
        self._idx_to_id: dict[int, str] = {}

    def init_index(self, dim: Optional[int] = None) -> None:
        """Initialize a new FAISS index.

        Args:
            dim: Vector dimension. Defaults to config value.
        """
        dim = dim or self.config.vector_dim
        self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))
        self._id_to_idx = {}
        self._idx_to_id = {}

    def add_memory(self, memory: MemoryNode) -> None:
        """Add a memory's embedding to the index.

        Args:
            memory: Memory node with an embedding vector.

        Raises:
            ValueError: If memory has no embedding.
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
        """Remove a memory from the index.

        Args:
            memory_id: The ID of the memory to remove.

        Note:
            FAISS doesn't support direct removal; this is a no-op placeholder.
        """
        pass

    def search(
        self, query_vector: list[float], k: int = 5
    ) -> list[tuple[str, float]]:
        """Search for the k nearest memories to a query vector.

        Args:
            query_vector: The query embedding vector.
            k: Number of neighbors to return.

        Returns:
            List of (memory_id, distance) tuples, sorted by distance.
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
        """Search using another memory's embedding as the query.

        Args:
            memory: The memory whose embedding serves as the query.
            k: Number of neighbors to return.

        Returns:
            List of (memory_id, distance) tuples.
        """
        if memory.embedding is None:
            return []
        return self.search(memory.embedding, k)

    def save_index(self, path: str) -> None:
        """Save the index to disk.

        Args:
            path: File path for the index file.
        """
        if self.index is not None:
            faiss.write_index(self.index, path)

    def load_index(self, path: str) -> None:
        """Load an index from disk.

        Args:
            path: File path to the index file.
        """
        self.index = faiss.read_index(path)
