"""Generic wrapper pattern for CLI/agent tools like Codex or Claude Code."""

from __future__ import annotations

import requests


BASE_URL = "http://127.0.0.1:8002"


def pre_prompt(query: str, persona: str) -> str:
    response = requests.post(
        f"{BASE_URL}/agent/context",
        json={
            "query": query,
            "persona": persona,
            "limit": 6,
            "system_prefix": "Relevant memory context:",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["context"]


def post_turn(user_input: str, assistant_output: str, persona: str) -> None:
    requests.post(
        f"{BASE_URL}/agent/store",
        json={
            "content": f"User: {user_input}\nAssistant: {assistant_output}",
            "persona": persona,
            "importance": 0.55,
            "source_type": "system",
            "memory_kind": "episodic",
            "confidence": 0.75,
        },
        timeout=30,
    ).raise_for_status()
