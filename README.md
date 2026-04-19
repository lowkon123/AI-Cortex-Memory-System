# Cortex Memory Engine

A local AI memory system designed to feel closer to human memory than a plain note store or vector database.

Instead of treating memory as static documents, Cortex Memory Engine treats memory as something that can be:

- formed
- compressed
- recalled
- reinforced
- consolidated
- forgotten

The goal is simple:

`maximize useful recall while minimizing prompt/context cost`

## What This Project Is

Cortex Memory Engine is a reusable memory layer for AI systems.

It includes:

- a memory dashboard for visual inspection
- a chat demo wired into the memory system
- a local REST API that other AI tools can call
- ranking, reinforcement, forgetting, and sleep-cycle logic

This means it can act as:

- a standalone AI memory experiment
- a local second-brain backend
- a plug-in memory service for tools like Claude Code, Codex, Antigravity, OpenWebUI, or custom agents

## Core Ideas

- Hierarchical memory: `L0 / L1 / L2`
- Dynamic recall: similarity is not enough; activation matters
- Token efficiency: summaries first, details on demand
- Reinforcement: useful memories get stronger
- Forgetting: stale or weak memories fade
- Sleep cycle: memories can be consolidated in the background
- Persona isolation: different AIs can share one memory service without sharing all memories

## Main Components

### Dashboard

- File: [dashboard.py](/d:/Projects/Antigravity/AI_mem_system/dashboard.py)
- Visual 3D memory graph
- Memory detail panel
- Stats and timeline views

### Chat Demo

- File: [chat.py](/d:/Projects/Antigravity/AI_mem_system/chat.py)
- Uses memory recall before generation
- Stores dialogue back into memory after the turn
- Reinforces recalled memories after successful use

### Reusable API

- Folder: [api](/d:/Projects/Antigravity/AI_mem_system/api)
- Exposes memory CRUD, search, and AI-facing integration endpoints

### Memory Core

- Folder: [src](/d:/Projects/Antigravity/AI_mem_system/src)
- Data model, ranking, context building, forgetting, feedback, graph recall, and sleep-cycle logic

## Key Features

- 3D memory visualization
- Double-click memory inspection
- Memory activation scoring
- Confidence and emotional weighting
- Concept tags
- Persona-aware recall
- Reinforcement feedback
- Sleep report
- API-based external integration

## Current Ports

Typical defaults:

- Dashboard: `http://127.0.0.1:8000`
- Memory API: `http://127.0.0.1:8002`

If `8000` is already occupied or you need a clean dashboard instance:

- [run_dashboard_8001.py](/d:/Projects/Antigravity/AI_mem_system/run_dashboard_8001.py)
- Dashboard alt port: `http://127.0.0.1:8001`

## Run The Dashboard

```bash
python dashboard.py
```

Open:

- `http://127.0.0.1:8000`
- timeline: `http://127.0.0.1:8000/timeline`

If needed:

```bash
python run_dashboard_8001.py
```

## Run The Chat Demo

```bash
python chat.py
```

What it does:

- chooses a model
- chooses a persona
- recalls relevant memories before answering
- stores the turn afterward
- reinforces memories that helped

## Run The API

### Docker

```bash
docker-compose up -d
```

Then open:

- API root: `http://127.0.0.1:8002`
- docs: `http://127.0.0.1:8002/docs`

### Direct

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8002
```

## API Integration Pattern

Any external AI can use Cortex with this loop:

1. `POST /agent/context`
2. append returned context to the model prompt
3. call the model
4. `POST /agent/store`
5. optionally `POST /agent/reinforce`

This is the shortest path to plugging Cortex into another AI system.

## Most Useful API Endpoints

### AI-facing

- `POST /agent/store`
- `POST /agent/recall`
- `POST /agent/context`
- `POST /agent/reinforce`

### Search and CRUD

- `POST /memories/`
- `GET /memories/{id}`
- `GET /memories/`
- `PATCH /memories/{id}`
- `DELETE /memories/{id}`
- `POST /memories/feedback`
- `POST /search/`
- `GET /search/by-tags`
- `GET /search/stats`

## Python Client Example

```python
from api.client import MemoryClient

client = MemoryClient("http://127.0.0.1:8002", persona="codex")

context = client.build_context("What does the user prefer?", limit=5)

# Put `context` into the system prompt before model generation

client.agent_store(
    content="User prefers concise engineering answers.",
    tags=["preferences", "style"],
    memory_kind="semantic",
    importance=0.8,
)

recall = client.recall("What does the user prefer?", limit=3)
memory_ids = [m["id"] for m in recall["memories"]]
if memory_ids:
    client.reinforce(memory_ids, boost=0.15)

client.close()
```

## Integration Targets

This project is now shaped to be usable by:

- Claude Code
- Codex
- Antigravity
- OpenWebUI
- custom Python agents
- any tool that can call local HTTP endpoints

Reference examples:

- [api/examples/python_agent_example.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/python_agent_example.py)
- [api/examples/openwebui_memory_tool.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/openwebui_memory_tool.py)
- [api/examples/cli_memory_wrapper.py](/d:/Projects/Antigravity/AI_mem_system/api/examples/cli_memory_wrapper.py)

## Data Model Highlights

Memories can carry:

- `importance`
- `importance_boost`
- `confidence`
- `emotional_weight`
- `concept_tags`
- `source_type`
- `memory_kind`
- `activation_score`
- `success_count`
- `consolidation_count`

This gives you more than a normal note store or vector search stack.

## Tests

Core cognition logic tests live in:

- [tests/test_memory_cognition.py](/d:/Projects/Antigravity/AI_mem_system/tests/test_memory_cognition.py)

Run:

```bash
pytest tests/test_memory_cognition.py -q
```

## Project Structure

```text
AI_mem_system/
├─ api/                  Reusable memory API and integration examples
├─ src/                  Core memory logic
├─ tests/                Tests
├─ chat.py               Chat demo
├─ dashboard.py          Dashboard server
├─ run_dashboard_8001.py Alternate dashboard port
├─ docker-compose.yml    Local API + Postgres stack
└─ implementation_plan.md
```

## Positioning

This is not just a note app.

It is better described as:

`a local, reusable AI memory layer that models recall, compression, reinforcement, and forgetting`

Or even shorter:

`not document storage, but memory for thinking systems`
