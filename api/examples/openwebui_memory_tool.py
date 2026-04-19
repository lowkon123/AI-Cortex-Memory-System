"""OpenWebUI-compatible tool example for Cortex Memory API.

Drop the core logic into an OpenWebUI Tool / Function and adjust metadata
to match your OpenWebUI version.
"""

from __future__ import annotations

import requests


BASE_URL = "http://127.0.0.1:8002"
PERSONA = "openwebui"


def recall_memory(query: str, limit: int = 5) -> str:
    response = requests.post(
        f"{BASE_URL}/agent/context",
        json={
            "query": query,
            "persona": PERSONA,
            "limit": limit,
            "system_prefix": "Relevant memory context for OpenWebUI:",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["context"]


def store_memory(content: str, tags: list[str] | None = None) -> dict:
    response = requests.post(
        f"{BASE_URL}/agent/store",
        json={
            "content": content,
            "persona": PERSONA,
            "tags": tags or [],
            "importance": 0.6,
            "source_type": "system",
            "memory_kind": "episodic",
            "confidence": 0.8,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
