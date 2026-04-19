"""Minimal example for any Python AI app."""

from api.client import MemoryClient


client = MemoryClient("http://127.0.0.1:8002", persona="codex")

# Store durable memory
client.agent_store(
    content="The user prefers concise engineering answers with direct action items.",
    tags=["preferences", "style"],
    importance=0.8,
    memory_kind="semantic",
    source_type="user",
    confidence=0.9,
)

# Build recall context before model generation
context = client.build_context("How should I answer this user?", limit=5)
print(context)

# After successful use, reinforce recalled memories
recall = client.recall("How should I answer this user?", limit=3)
memory_ids = [m["id"] for m in recall["memories"]]
if memory_ids:
    client.reinforce(memory_ids, boost=0.15)

client.close()
