"""Semantic and tag search routes."""

from __future__ import annotations

import os
from typing import Optional

import asyncpg
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/search", tags=["search"])

EMBEDDING_API = os.getenv("EMBEDDING_API", "http://localhost:11434/api/embeddings")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")


async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    persona: str = Field(default="default", description="Filter by persona")
    limit: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    id: str
    content: str
    persona: str
    importance: float
    tags: list[str]
    similarity: float
    created_at: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


async def get_embedding(text: str) -> list[float]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                EMBEDDING_API,
                json={"model": EMBEDDING_MODEL, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service unavailable: {e}",
        ) from e


@router.post("/", response_model=SearchResponse)
async def semantic_search(request: SearchRequest, http_request: Request):
    query_embedding = await get_embedding(request.query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")

    pool = await get_pool(http_request)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                content,
                persona,
                importance,
                concept_tags,
                created_at,
                1 - (embedding <-> $1::vector) AS similarity
            FROM memories
            WHERE status = 'active'
              AND persona = $2
              AND embedding IS NOT NULL
              AND 1 - (embedding <-> $1::vector) >= $3
            ORDER BY embedding <-> $1::vector
            LIMIT $4
            """,
            query_embedding,
            request.persona,
            request.min_similarity,
            request.limit,
        )

        if rows:
            memory_ids = [row["id"] for row in rows]
            await conn.execute(
                """
                UPDATE memories
                SET access_count = access_count + 1,
                    last_accessed = NOW()
                WHERE id = ANY($1::uuid[])
                """,
                memory_ids,
            )

    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(
                id=str(row["id"]),
                content=row["content"],
                persona=row["persona"],
                importance=row["importance"],
                tags=row["concept_tags"] or [],
                similarity=round(float(row["similarity"]), 4),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ],
        total=len(rows),
    )


@router.get("/by-tags", response_model=SearchResponse)
async def search_by_tags(
    http_request: Request,
    tags: str = Query(..., description="Comma-separated tags"),
    persona: str = Query(default="default"),
    limit: int = Query(default=10, ge=1, le=50),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    pool = await get_pool(http_request)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, content, persona, importance, concept_tags, created_at
            FROM memories
            WHERE status = 'active'
              AND persona = $1
              AND concept_tags && $2::text[]
            ORDER BY importance DESC, created_at DESC
            LIMIT $3
            """,
            persona,
            tag_list,
            limit,
        )

    return SearchResponse(
        query=tags,
        results=[
            SearchResult(
                id=str(row["id"]),
                content=row["content"],
                persona=row["persona"],
                importance=row["importance"],
                tags=row["concept_tags"] or [],
                similarity=1.0,
                created_at=str(row["created_at"]),
            )
            for row in rows
        ],
        total=len(rows),
    )


@router.get("/stats")
async def get_stats(
    http_request: Request,
    persona: Optional[str] = Query(default=None),
):
    pool = await get_pool(http_request)

    where_clause = "WHERE status = 'active'"
    params: list = []
    if persona:
        where_clause += " AND persona = $1"
        params.append(persona)

    async with pool.acquire() as conn:
        stats = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*) AS total_memories,
                COUNT(embedding) AS vectorized_memories,
                AVG(importance) AS avg_importance,
                SUM(access_count) AS total_accesses
            FROM memories
            {where_clause}
            """,
            *params,
        )

    return {
        "total_memories": stats["total_memories"],
        "vectorized_memories": stats["vectorized_memories"],
        "avg_importance": round(float(stats["avg_importance"] or 0), 3),
        "total_accesses": stats["total_accesses"] or 0,
        "persona": persona or "all",
    }
