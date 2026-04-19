"""Cortex Memory API Server."""

from __future__ import annotations

from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import db_config
from .routes import agent, memories, search


async def _setup_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "vector",
        encoder=lambda v: "[" + ",".join(str(float(x)) for x in v) + "]",
        decoder=lambda v: [float(x) for x in v[1:-1].split(",")] if v and len(v) > 2 else [],
        schema="public",
        format="text",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await asyncpg.create_pool(
        **db_config.asyncpg_kwargs,
        min_size=2,
        max_size=10,
        setup=_setup_connection,
    )
    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(
    title="Cortex Memory API",
    description="""
## Memory API for AI Agents

A reusable REST interface for AI tools to store, search, reinforce, and retrieve memories.

### Quick Start

Store:
```bash
curl -X POST http://localhost:8002/memories/ \
  -H "Content-Type: application/json" \
  -d '{"content":"User prefers dark mode","persona":"openclaw"}'
```

Search:
```bash
curl -X POST http://localhost:8002/search/ \
  -H "Content-Type: application/json" \
  -d '{"query":"user preferences","persona":"openclaw"}'
```

List:
```bash
curl "http://localhost:8002/memories/?persona=openclaw"
```
""",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(memories.router)
app.include_router(search.router)
app.include_router(agent.router)


@app.get("/", tags=["health"])
async def root():
    return {
        "status": "healthy",
        "service": "Cortex Memory API",
        "version": "0.1.0",
    }


@app.get("/health", tags=["health"])
async def health():
    return {
        "status": "healthy",
        "database": "connected",
        "vector_search": "available",
    }


@app.get("/personas", tags=["info"])
async def list_personas():
    return {
        "default": "Default persona for general memories",
        "openclaw": "OpenClaw AI assistant",
        "claude": "Claude Code",
        "codex": "Codex / Copilot",
        "antigravity": "Antigravity AI",
        "custom": "Use any custom string as persona identifier",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
