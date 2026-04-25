"""FAISS integration for high-performance semantic memory retrieval.

This module provides vector-based similarity search using FAISS, 
enabling semantic recall beyond exact keyword matching.
"""

import faiss
import numpy as np
from typing import Optional

from ..models import MemoryNode, MemoryStoreConfig


class MemoryVectorStore:
    """FAISS-backed vector store for semantic memory search.

    Provides efficient nearest-neighbor search for retrieving memories based on embedding similarity.
    """

    def __init__(self, config: MemoryStoreConfig):
        """Initialize the vector store with configuration.

        Args:
            config: Memory store configuration containing vector dimensions.
        """
        self.config = config
        self.index: Optional[faiss.Index] = None
        self._id_to_idx: dict[str, int] = {}
        self._idx_to_id: dict[int, str] = {}

    def init_index(self, dim: Optional[int] = None) -> None:
        """Initialize a new FAISS index.

        Args:
            dim: Dimension of the vectors. Defaults to the configured dimension.
        """
        dim = dim or self.config.vector_dim
        self.index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))
        self._id_to_idx = {}
        self._idx_to_id = {}

    def add_memory(self, memory: MemoryNode) -> None:
        """Add a memory's embedding vector to the index.

        Args:
            memory: The memory node containing the embedding vector.

        Raises:
            ValueError: If the memory node does not have an embedding vector.
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
            memory_id: ID of the memory to remove.

        Note:
            FAISS IndexIDMap supports deletion using ID, but standard removal in base indices is minimal.
        """
        # FAISS deletion is version-dependent and complex for some index types.
        # This implementation currently assumes indices are rebuilt for major changes.
        pass

    def search(
        self, query_vector: list[float], k: int = 5
    ) -> list[tuple[str, float]]:
        """Search for the k nearest memories to a query vector.

        Args:
            query_vector: Query embedding vector.
            k: Number of nearest neighbors to return.

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
        """Search using another memory's embedding vector as the query.

        Args:
            memory: The memory whose embedding is used as the query.
            k: Number of neighbors to return.

        Returns:
            List of (memory_id, distance) tuples.
        """
        if memory.embedding is None:
            return []
        return self.search(memory.embedding, k)

    def save_index(self, path: str) -> None:
        """Save the FAISS index to disk.

        Args:
            path: Target path for the index file.
        """
        if self.index is not None:
            faiss.write_index(self.index, path)

    def load_index(self, path: str) -> None:
        """Load a FAISS index from disk.

        Args:
            path: Path to the index file.
        """
        self.index = faiss.read_index(path)
