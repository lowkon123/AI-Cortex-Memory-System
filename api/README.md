# Cortex Memory API

A reusable local memory layer for AI tools.

This API is designed so systems like `Claude Code`, `Codex`, `Antigravity`, `OpenWebUI`, or any custom agent can:

- store durable memories
- recall relevant memories before generation
- build prompt-ready memory context
- reinforce memories after a successful turn

## Run

```bash
docker-compose up -d
```

API:
- `http://localhost:8002`
- docs: `http://localhost:8002/docs`

## Core Integration Flow

Any AI can use this loop:

1. `POST /agent/context`
2. append returned context to the model prompt
3. call the model
4. `POST /agent/store`
5. optionally `POST /agent/reinforce`

## Main Endpoints

### Low-level CRUD

- `POST /memories/`
- `GET /memories/{id}`
- `GET /memories/`
- `PATCH /memories/{id}`
- `DELETE /memories/{id}`
- `POST /memories/feedback`

### Search

- `POST /search/`
- `GET /search/by-tags`
- `GET /search/stats`

### AI-facing Endpoints

- `POST /agent/store`
- `POST /agent/recall`
- `POST /agent/context`
- `POST /agent/reinforce`

## Examples

See:

- [examples/python_agent_example.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/python_agent_example.py)
- [examples/openwebui_memory_tool.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/openwebui_memory_tool.py)
- [examples/cli_memory_wrapper.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/cli_memory_wrapper.py)

## Example: generic AI app

```python
from api.client import MemoryClient

client = MemoryClient("http://127.0.0.1:8002", persona="claude")
context = client.build_context("What does the user prefer?", limit=5)

# put `context` into the model prompt

client.agent_store(
    content="User prefers concise engineering answers.",
    tags=["preferences", "style"],
    memory_kind="semantic",
    importance=0.8,
)
```

## Example: OpenWebUI tool pattern

Use `/agent/context` before model generation and `/agent/store` after the turn.

## Example: Claude Code / Codex / CLI agent pattern

Wrap your tool loop like this:

- before prompt: call `/agent/context`
- after successful answer: call `/agent/store`
- after especially useful recall: call `/agent/reinforce`

## Personas

Use one persona per AI:

- `claude`
- `codex`
- `antigravity`
- `openwebui`
- or any custom string

This keeps memories separated while sharing the same memory service.
