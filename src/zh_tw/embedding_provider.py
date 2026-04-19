"""Ollama-based embedding provider for the Cortex Memory Engine."""

import httpx
from typing import List, Optional


class OllamaEmbeddingProvider:
    """Provides vector embeddings using a local Ollama instance."""

    def __init__(self, model: str = "bge-m3", base_url: str = "http://localhost:11434"):
        """Initialize the provider.

        Args:
            model: The Ollama model name for embeddings.
            base_url: The URL where Ollama is running.
        """
        self.model = model
        self.base_url = base_url

    async def get_embedding(self, text: str) -> list[float]:
        """Fetch embedding for a single string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the vector.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Fetch embeddings for multiple strings.

        Args:
            texts: List of text strings.

        Returns:
            List of embedding vectors.
        """
        # Ollama's /api/embeddings often only takes one prompt at a time 
        # (depending on version), so we iterate for safety.
        return [await self.get_embedding(text) for text in texts]
