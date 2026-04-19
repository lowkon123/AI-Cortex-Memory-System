"""Agent-oriented routes for plug-and-play AI integrations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .search import get_embedding

router = APIRouter(prefix="/agent", tags=["agent"])


async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


def utc_now() -> datetime:
    return datetime.now(UTC)


class StoreMemoryRequest(BaseModel):
    content: str = Field(..., min_length=1)
    persona: str = Field(default="default")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    source_type: str = Field(default="user")
    memory_kind: str = Field(default="episodic")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    emotional_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    with_embedding: bool = Field(default=True)


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=1)
    persona: str = Field(default="default")
    limit: int = Field(default=6, ge=1, le=20)
    min_similarity: float = Field(default=0.45, ge=0.0, le=1.0)
    include_context: bool = True
    system_prefix: str = "Relevant memory context:"


class ReinforceRequest(BaseModel):
    memory_ids: list[str] = Field(..., min_length=1)
    boost_amount: float = Field(default=0.1, ge=0.0, le=1.0)


class BuildContextRequest(BaseModel):
    query: str = Field(..., min_length=1)
    persona: str = Field(default="default")
    limit: int = Field(default=6, ge=1, le=20)
    system_prefix: str = "Relevant memory context:"


def _compose_context(memories: list[dict], system_prefix: str) -> str:
    if not memories:
        return f"{system_prefix}\n- No relevant memory found."
    lines = [system_prefix]
    for idx, memory in enumerate(memories, start=1):
        tags = ", ".join(memory["tags"][:4]) if memory["tags"] else "no-tags"
        lines.append(
            f"{idx}. score={memory['score']:.3f} sim={memory['similarity']:.3f} "
            f"importance={memory['importance']:.2f} tags={tags}"
        )
        lines.append(f"   {memory['content']}")
    return "\n".join(lines)


@router.post("/store")
async def store_memory(payload: StoreMemoryRequest, request: Request):
    pool = await get_pool(request)
    now = utc_now()
    embedding = await get_embedding(payload.content) if payload.with_embedding else None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memories (
                id, content, persona, importance, concept_tags, session_id,
                source_type, memory_kind, confidence, emotional_weight,
                embedding, created_at, updated_at, status
            )
            VALUES (
                $1, $2, $3, $4, $5::text[], $6::uuid, $7, $8, $9, $10,
                $11::vector, $12, $13, 'active'
            )
            RETURNING id, persona, content, importance, concept_tags,
                      source_type, memory_kind, confidence, emotional_weight,
                      created_at, updated_at
            """,
            str(uuid4()),
            payload.content,
            payload.persona,
            payload.importance,
            payload.tags,
            payload.session_id,
            payload.source_type,
            payload.memory_kind,
            payload.confidence,
            payload.emotional_weight,
            embedding,
            now,
            now,
        )

    return {
        "ok": True,
        "memory": {
            "id": str(row["id"]),
            "persona": row["persona"],
            "content": row["content"],
            "importance": row["importance"],
            "tags": row["concept_tags"] or [],
            "source_type": row["source_type"],
            "memory_kind": row["memory_kind"],
            "confidence": row["confidence"],
            "emotional_weight": row["emotional_weight"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        },
    }


@router.post("/recall")
async def recall_memories(payload: RecallRequest, request: Request):
    query_embedding = await get_embedding(payload.query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")

    pool = await get_pool(request)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                content,
                persona,
                importance,
                concept_tags,
                access_count,
                success_count,
                confidence,
                emotional_weight,
                source_type,
                memory_kind,
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
            payload.persona,
            payload.min_similarity,
            payload.limit,
        )

        memories = []
        for row in rows:
            similarity = float(row["similarity"])
            score = (
                similarity * 0.45
                + float(row["importance"]) * 0.2
                + min(1.0, (row["access_count"] or 0) / 10) * 0.1
                + min(1.0, (row["success_count"] or 0) / 8) * 0.1
                + float(row["confidence"] or 0) * 0.1
                + float(row["emotional_weight"] or 0) * 0.05
            )
            memories.append(
                {
                    "id": str(row["id"]),
                    "content": row["content"],
                    "persona": row["persona"],
                    "importance": float(row["importance"]),
                    "tags": row["concept_tags"] or [],
                    "access_count": row["access_count"] or 0,
                    "success_count": row["success_count"] or 0,
                    "confidence": float(row["confidence"] or 0),
                    "emotional_weight": float(row["emotional_weight"] or 0),
                    "source_type": row["source_type"],
                    "memory_kind": row["memory_kind"],
                    "created_at": row["created_at"].isoformat(),
                    "similarity": round(similarity, 4),
                    "score": round(score, 4),
                }
            )

        memories.sort(key=lambda item: item["score"], reverse=True)

        if memories:
            ids = [m["id"] for m in memories]
            await conn.execute(
                """
                UPDATE memories
                SET access_count = access_count + 1,
                    last_accessed = NOW()
                WHERE id = ANY($1::uuid[])
                """,
                ids,
            )

    context = _compose_context(memories, payload.system_prefix) if payload.include_context else ""
    return {
        "query": payload.query,
        "persona": payload.persona,
        "total": len(memories),
        "context": context,
        "memories": memories,
    }


@router.post("/context")
async def build_context(payload: BuildContextRequest, request: Request):
    recall = await recall_memories(
        RecallRequest(
            query=payload.query,
            persona=payload.persona,
            limit=payload.limit,
            include_context=True,
            system_prefix=payload.system_prefix,
        ),
        request,
    )
    return {
        "query": payload.query,
        "persona": payload.persona,
        "context": recall["context"],
        "memories": recall["memories"],
    }


@router.post("/reinforce")
async def reinforce_memories(payload: ReinforceRequest, request: Request):
    pool = await get_pool(request)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE memories
            SET success_count = success_count + 1,
                importance_boost = LEAST(1.0, importance_boost + $2),
                last_reinforced = NOW()
            WHERE id = ANY($1::uuid[])
            """,
            payload.memory_ids,
            payload.boost_amount,
        )
    return {"ok": True, "reinforced": len(payload.memory_ids), "boost_amount": payload.boost_amount}
