"""Cortex 2.0 Knowledge Extraction Pipeline.

This module transforms raw conversation content into structured Facts and Episodes, 
supporting version control and correlation detection.
"""

import json
import httpx
from typing import Any, Optional
from uuid import UUID

from ..models import MemoryNode, MemoryKind, MemorySource, MemoryStatus


class FactExtractionPipeline:
    """Pipeline for extracting structured knowledge from raw data."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        """Initialize extraction pipeline.

        Args:
            model: Ollama model name.
            base_url: Ollama API endpoint.
        """
        self.model = model
        self.base_url = base_url

    async def extract_structured_knowledge(self, content: str) -> list[dict[str, Any]]:
        """Extract facts, entities, and relationships from content."""
        prompt = f"""Analyze the following conversation content and extract structured knowledge.
**Crucial: All extracted text must be in ENGLISH, even if the input is in Chinese.**

Extraction Goals:
1. **Fact**: Persistent information (e.g., User likes React, User lives in Taipei).
2. **Episode**: Behavioral events at a specific time (e.g., User is adjusting database indices, User reinstalled the computer today).
3. **Concept**: Important entities or terms mentioned (e.g., pgvector, React, Docker).

Rules:
- Return a JSON array of objects. Each object must contain:
  - "type": "fact" | "episode" | "concept"
  - "content": A brief description (MUST BE IN ENGLISH).
  - "importance": Importance score (0.0 - 1.0).
  - "metadata": Structured attributes.
  - "supersedes": Optional.

Content:
{content}

Return ONLY the JSON array:"""

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=120.0,
                )
                response.raise_for_status()
                raw = response.json()["response"].strip()

                if raw.startswith("```"):
                    lines = raw.split("\n")
                    lines = [l for l in lines if not l.startswith("```")]
                    raw = "\n".join(lines).strip()

                items = json.loads(raw)
                if not isinstance(items, list):
                    return []
                return items
            except Exception:
                return []

    def create_node_from_extracted(self, item: dict[str, Any], session_id: Optional[UUID] = None) -> MemoryNode:
        """Transform an extracted item into a MemoryNode object."""
        kind_map = {
            "fact": MemoryKind.SEMANTIC,
            "episode": MemoryKind.EPISODIC,
            "concept": MemoryKind.CONCEPT
        }
        
        kind = kind_map.get(item.get("type", "fact"), MemoryKind.SEMANTIC)
        
        return MemoryNode(
            content=item["content"],
            importance=item.get("importance", 0.5),
            memory_kind=kind,
            source_type=MemorySource.INFERRED,
            session_id=session_id,
            metadata=item.get("metadata", {}),
            status=MemoryStatus.ACTIVE
        )


async def extract_facts(content: str, model: str, base_url: str = "http://localhost:11434") -> list[str]:
    """Standalone compatibility wrapper for fact extraction."""
    pipeline = FactExtractionPipeline(model, base_url)
    items = await pipeline.extract_structured_knowledge(content)
    return [item["content"] for item in items if "content" in item]
