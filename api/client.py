"""Simple Python client for Cortex Memory API.

Usage:
    from api.client import MemoryClient

    client = MemoryClient('http://localhost:8002')
    client.store('User prefers dark mode', persona='openclaw')
    results = client.search('user preferences', persona='openclaw')
"""

import httpx
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Memory:
    """A memory object."""

    id: str
    content: str
    persona: str
    importance: float
    tags: list[str]
    created_at: datetime
    access_count: int = 0
    similarity: float = 0.0
    score: float = 0.0


class MemoryClient:
    """Simple client for interacting with Cortex Memory API."""

    def __init__(self, base_url: str = 'http://localhost:8002', persona: str = 'default'):
        self.base_url = base_url.rstrip('/')
        self.persona = persona
        self.client = httpx.Client(timeout=30.0)

    def store(self, content: str, importance: float = 0.5, tags: Optional[list[str]] = None) -> Memory:
        """Store a new memory."""
        response = self.client.post(
            f'{self.base_url}/memories/',
            json={
                'content': content,
                'persona': self.persona,
                'importance': importance,
                'tags': tags or [],
            }
        )
        response.raise_for_status()
        data = response.json()
        return Memory(
            id=data['id'],
            content=data['content'],
            persona=data['persona'],
            importance=data['importance'],
            tags=data['tags'],
            created_at=datetime.fromisoformat(data['created_at'].replace('Z', '+00:00')),
            access_count=data['access_count'],
        )

    def agent_store(
        self,
        content: str,
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        source_type: str = "user",
        memory_kind: str = "episodic",
        confidence: float = 0.7,
        emotional_weight: float = 0.0,
    ) -> dict:
        response = self.client.post(
            f"{self.base_url}/agent/store",
            json={
                "content": content,
                "persona": self.persona,
                "importance": importance,
                "tags": tags or [],
                "session_id": session_id,
                "source_type": source_type,
                "memory_kind": memory_kind,
                "confidence": confidence,
                "emotional_weight": emotional_weight,
            },
        )
        response.raise_for_status()
        return response.json()

    def search(self, query: str, limit: int = 5) -> list[Memory]:
        """Search memories by semantic similarity."""
        response = self.client.post(
            f'{self.base_url}/search/',
            json={
                'query': query,
                'persona': self.persona,
                'limit': limit,
            }
        )
        response.raise_for_status()
        data = response.json()
        return [
            Memory(
                id=r['id'],
                content=r['content'],
                persona=r['persona'],
                importance=r['importance'],
                tags=r['tags'],
                created_at=datetime.fromisoformat(r['created_at'].replace('Z', '+00:00')),
            )
            for r in data['results']
        ]

    def recall(self, query: str, limit: int = 6, system_prefix: str = "Relevant memory context:") -> dict:
        response = self.client.post(
            f"{self.base_url}/agent/recall",
            json={
                "query": query,
                "persona": self.persona,
                "limit": limit,
                "include_context": True,
                "system_prefix": system_prefix,
            },
        )
        response.raise_for_status()
        return response.json()

    def build_context(self, query: str, limit: int = 6, system_prefix: str = "Relevant memory context:") -> str:
        response = self.client.post(
            f"{self.base_url}/agent/context",
            json={
                "query": query,
                "persona": self.persona,
                "limit": limit,
                "system_prefix": system_prefix,
            },
        )
        response.raise_for_status()
        return response.json()["context"]

    def list(self, limit: int = 20) -> list[Memory]:
        """List recent memories."""
        response = self.client.get(
            f'{self.base_url}/memories/',
            params={'persona': self.persona, 'limit': limit}
        )
        response.raise_for_status()
        return [
            Memory(
                id=m['id'],
                content=m['content'],
                persona=m['persona'],
                importance=m['importance'],
                tags=m['tags'],
                created_at=datetime.fromisoformat(m['created_at'].replace('Z', '+00:00')),
                access_count=m['access_count'],
            )
            for m in response.json()
        ]

    def feedback(self, memory_id: str, success: bool = True, boost: float = 0.1):
        """Send feedback on memory usefulness."""
        response = self.client.post(
            f'{self.base_url}/memories/feedback',
            json={
                'memory_id': memory_id,
                'success': success,
                'boost_amount': boost,
            }
        )
        response.raise_for_status()

    def reinforce(self, memory_ids: list[str], boost: float = 0.1) -> dict:
        response = self.client.post(
            f"{self.base_url}/agent/reinforce",
            json={
                "memory_ids": memory_ids,
                "boost_amount": boost,
            },
        )
        response.raise_for_status()
        return response.json()

    def stats(self) -> dict:
        """Get memory statistics."""
        response = self.client.get(
            f'{self.base_url}/search/stats',
            params={'persona': self.persona}
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self.client.close()

