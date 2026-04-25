"""Advanced Retrieval Enhancer for Cortex Memory.
Implements HyDE (Hypothetical Document Embeddings) and Query Expansion.
"""

import json
import httpx
from typing import List
from src.core.embedding_provider import OllamaEmbeddingProvider

class RetrievalEnhancer:
    def __init__(self, provider: OllamaEmbeddingProvider, model: str = "gemma4:e2b"):
        self.provider = provider
        self.model = model
        self.base_url = "http://localhost:11434"

    async def generate_hyde_embedding(self, query: str) -> List[float]:
        """Generate a hypothetical answer and return its embedding."""
        prompt = f"""You are a memory retrieval assistant. Given the question below, generate a short, factual, hypothetical answer that would likely be found in a professional knowledge base.

Question: {query}

Hypothetical Answer:"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=30.0
                )
                hypothetical_answer = response.json()["response"].strip()
                
                # Use the hypothetical answer to get the embedding
                return await self.provider.get_embedding(hypothetical_answer)
        except Exception:
            # Fallback to direct query embedding
            return await self.provider.get_embedding(query)

    async def expand_query(self, query: str) -> List[str]:
        """Break down a complex query into multiple sub-queries."""
        prompt = f"""Break down the following complex user request into 2-3 specific, searchable sub-queries for a vector database.

Request: {query}

Return ONLY a JSON array of strings: ["query1", "query2", ...]"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=30.0
                )
                return json.loads(response.json()["response"])
        except Exception:
            return [query]
