# Cortex Memory Engine Integration Guide

This guide explains how to plug Cortex Memory Engine into other AI systems.

The goal is to make Cortex act like a local memory layer that sits around your model loop:

1. recall memory before generation
2. append the returned context to the prompt
3. run the model
4. store the useful result back into memory
5. optionally reinforce the memories that helped

## What You Need Running

Recommended local services:

- Dashboard: `http://127.0.0.1:8001`
- Memory API: `http://127.0.0.1:8002`
- API docs: `http://127.0.0.1:8002/docs`

If you are integrating another AI tool, the only required service is the API on `8002`.

## The Shortest Possible Integration

Every AI can use the same 3-endpoint pattern:

- `POST /agent/context`
- `POST /agent/store`
- `POST /agent/reinforce`

### Before model generation

Call:

```http
POST http://127.0.0.1:8002/agent/context
Content-Type: application/json
```

```json
{
  "query": "How should I answer this user?",
  "persona": "codex",
  "limit": 6,
  "system_prefix": "Relevant memory context:"
}
```

This returns:

```json
{
  "context": "Relevant memory context:\n1. ..."
}
```

Append the returned `context` into your system prompt before calling the model.

### After a successful answer

Call:

```http
POST http://127.0.0.1:8002/agent/store
Content-Type: application/json
```

```json
{
  "content": "User: I prefer concise answers.\nAssistant: Understood. I will keep answers tighter.",
  "persona": "codex",
  "importance": 0.65,
  "tags": ["preferences", "style"],
  "source_type": "system",
  "memory_kind": "episodic",
  "confidence": 0.85
}
```

### If recall was especially useful

Call:

```http
POST http://127.0.0.1:8002/agent/reinforce
Content-Type: application/json
```

```json
{
  "memory_ids": ["memory-id-1", "memory-id-2"],
  "boost_amount": 0.15
}
```

## Recommended Personas

Use one persona per AI tool so memories stay separated:

- `codex`
- `claude`
- `antigravity`
- `openwebui`
- `default`

You can also create app-specific personas such as:

- `codex-project-alpha`
- `claude-research`
- `openwebui-general`

## Integration Patterns

## 1. Generic HTTP AI

If your AI software can make HTTP requests, this is enough:

1. Before generation, call `/agent/context`
2. Inject the returned context into the prompt
3. Generate the answer
4. After the turn, call `/agent/store`
5. Optionally call `/agent/reinforce`

Prompt shape:

```text
[system]
You are a helpful assistant.

Relevant memory context:
1. ...
2. ...

[user]
How should you answer me?
```

## 2. Python AI App

Use the built-in client:

```python
from api.client import MemoryClient

client = MemoryClient("http://127.0.0.1:8002", persona="codex")

context = client.build_context("What does this user prefer?", limit=5)

# Add `context` into the model prompt here.

client.agent_store(
    content="User prefers concise engineering answers.",
    tags=["preferences", "style"],
    memory_kind="semantic",
    importance=0.8,
    source_type="user",
    confidence=0.9,
)

recall = client.recall("What does this user prefer?", limit=3)
memory_ids = [m["id"] for m in recall["memories"]]
if memory_ids:
    client.reinforce(memory_ids, boost=0.15)

client.close()
```

Reference:

- [api/client.py](/d:/Projects/Antigravity/AI_mem_system/api/client.py)
- [api/examples/python_agent_example.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/python_agent_example.py)

## 3. Codex or Claude Code Style CLI Agent

For tool-driven coding agents, Cortex should sit around the normal agent loop.

Suggested flow:

1. User gives a task
2. Agent calls `/agent/context` using the task or recent conversation as query
3. Agent prepends the returned memory context to its system prompt
4. Agent performs the task
5. Agent stores a compact turn summary through `/agent/store`
6. If the recalled memories clearly helped, call `/agent/reinforce`

Minimal wrapper idea:

```python
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
```

Reference:

- [api/examples/cli_memory_wrapper.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/cli_memory_wrapper.py)

Recommended personas:

- Codex: `codex`
- Claude Code: `claude`
- Antigravity agent: `antigravity`

## 4. OpenWebUI

OpenWebUI can use Cortex as a Tool or Function.

Recommended pattern:

1. Add a recall tool that calls `/agent/context`
2. Add a store tool that calls `/agent/store`
3. Use a dedicated persona like `openwebui`

Example tool logic:

```python
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
```

Reference:

- [api/examples/openwebui_memory_tool.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/openwebui_memory_tool.py)

## 5. Antigravity or Any Custom Agent Framework

Treat Cortex as a sidecar memory service on localhost.

Recommended architecture:

- your app handles model calls
- Cortex handles durable memory
- your app decides when to recall, store, and reinforce

This keeps the memory engine reusable instead of tying memory logic into one chat app.

## Which Endpoints To Use

### Best for most AI tools

- `POST /agent/context`
- `POST /agent/store`
- `POST /agent/reinforce`

### Best when you want structured recall results

- `POST /agent/recall`

This returns memory objects plus prompt-ready context.

### Best for lower-level control

- `POST /memories/`
- `GET /memories/{id}`
- `GET /memories/`
- `PATCH /memories/{id}`
- `DELETE /memories/{id}`
- `POST /memories/feedback`
- `POST /search/`
- `GET /search/by-tags`
- `GET /search/stats`

## Suggested Memory Policy

Use these rough defaults unless your app needs something special.

### Store as `episodic`

Use for:

- dialogue turns
- user requests
- short-lived interaction history
- task progress

### Store as `semantic`

Use for:

- stable user preferences
- known facts
- durable project context
- reusable operating rules

### Use `importance`

Suggested scale:

- `0.3` low value
- `0.5` normal
- `0.7` important
- `0.9` highly durable

### Use `confidence`

Suggested scale:

- `0.4` uncertain
- `0.7` plausible
- `0.9` strong confidence

## Example cURL Calls

### Build memory context

```bash
curl -X POST http://127.0.0.1:8002/agent/context ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"What does the user prefer?\",\"persona\":\"codex\",\"limit\":5}"
```

### Store memory

```bash
curl -X POST http://127.0.0.1:8002/agent/store ^
  -H "Content-Type: application/json" ^
  -d "{\"content\":\"User prefers concise answers.\",\"persona\":\"codex\",\"importance\":0.8,\"tags\":[\"preferences\"],\"memory_kind\":\"semantic\",\"source_type\":\"user\",\"confidence\":0.9}"
```

### Reinforce memory

```bash
curl -X POST http://127.0.0.1:8002/agent/reinforce ^
  -H "Content-Type: application/json" ^
  -d "{\"memory_ids\":[\"your-memory-id\"],\"boost_amount\":0.15}"
```

## Troubleshooting

### The dashboard shows nothing

Check the API first:

- `http://127.0.0.1:8002/`
- `http://127.0.0.1:8002/docs`

Then check the dashboard:

- `http://127.0.0.1:8001/`

### My AI can store but not recall

Check:

- the API is running on `8002`
- the same `persona` is being used for both store and recall
- your query actually overlaps with stored content or tags

### Memories are mixed between tools

Use separate personas for each AI system.

### I want one shared memory across multiple tools

Use the same persona intentionally, for example:

- `team-shared`

## Recommended Next Step

If you are integrating Cortex into a new AI system, start with this:

1. hardcode persona
2. call `/agent/context` before generation
3. call `/agent/store` after each useful turn
4. add `/agent/reinforce` later

That gives you the fastest working integration with the least code.
