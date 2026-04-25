"""Memory CRUD routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/memories", tags=["memories"])


def utc_now() -> datetime:
    return datetime.now(UTC)


async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, description="The memory content text")
    persona: str = Field(default="default", description="AI persona identifier")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    session_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tags: Optional[list[str]] = None
    summary_l1: Optional[str] = None
    summary_l0: Optional[str] = None


class MemoryResponse(BaseModel):
    id: str
    content: str
    persona: str
    importance: float
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    access_count: int = 0


class FeedbackRequest(BaseModel):
    memory_id: str
    success: bool = Field(..., description="Whether the memory was useful")
    boost_amount: float = Field(default=0.1, ge=0.0, le=1.0)


@router.post("/", response_model=MemoryResponse, status_code=201)
async def create_memory(memory: MemoryCreate, request: Request):
    pool = await get_pool(request)
    now = utc_now()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memories (
                id, content, persona, importance, concept_tags, session_id,
                created_at, updated_at, status
            )
            VALUES ($1, $2, $3, $4, $5::text[], $6::uuid, $7, $8, 'active')
            RETURNING id, content, persona, importance, concept_tags,
                      created_at, updated_at, access_count
            """,
            str(uuid4()),
            memory.content,
            memory.persona,
            memory.importance,
            memory.tags,
            memory.session_id,
            now,
            now,
        )

    return MemoryResponse(
        id=str(row["id"]),
        content=row["content"],
        persona=row["persona"],
        importance=row["importance"],
        tags=row["concept_tags"] or [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        access_count=row["access_count"],
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str, request: Request):
    pool = await get_pool(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE memories
            SET access_count = access_count + 1,
                last_accessed = NOW()
            WHERE id = $1::uuid
              AND status = 'active'
            RETURNING id, content, persona, importance, concept_tags,
                      created_at, updated_at, access_count
            """,
            memory_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryResponse(
        id=str(row["id"]),
        content=row["content"],
        persona=row["persona"],
        importance=row["importance"],
        tags=row["concept_tags"] or [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        access_count=row["access_count"],
    )


@router.get("/", response_model=list[MemoryResponse])
async def list_memories(
    request: Request,
    persona: Optional[str] = Query(default="default", description="Filter by persona"),
    limit: int = Query(default=20, ge=1, le=100),
):
    pool = await get_pool(request)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, content, persona, importance, concept_tags,
                   created_at, updated_at, access_count
            FROM memories
            WHERE status = 'active'
              AND persona = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            persona,
            limit,
        )

    return [
        MemoryResponse(
            id=str(row["id"]),
            content=row["content"],
            persona=row["persona"],
            importance=row["importance"],
            tags=row["concept_tags"] or [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
        )
        for row in rows
    ]


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_id: str, update: MemoryUpdate, request: Request):
    updates = []
    values = [memory_id]
    idx = 2

    if update.content is not None:
        updates.append(f"content = ${idx}")
        values.append(update.content)
        idx += 1
    if update.importance is not None:
        updates.append(f"importance = ${idx}")
        values.append(update.importance)
        idx += 1
    if update.tags is not None:
        updates.append(f"concept_tags = ${idx}::text[]")
        values.append(update.tags)
        idx += 1
    if update.summary_l1 is not None:
        updates.append(f"summary_l1 = ${idx}")
        values.append(update.summary_l1)
        idx += 1
    if update.summary_l0 is not None:
        updates.append(f"summary_l0 = ${idx}")
        values.append(update.summary_l0)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")
    query = f"""
        UPDATE memories
        SET {", ".join(updates)}
        WHERE id = $1::uuid
          AND status = 'active'
        RETURNING id, content, persona, importance, concept_tags,
                  created_at, updated_at, access_count
    """

    pool = await get_pool(request)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)

    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryResponse(
        id=str(row["id"]),
        content=row["content"],
        persona=row["persona"],
        importance=row["importance"],
        tags=row["concept_tags"] or [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        access_count=row["access_count"],
    )


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, request: Request):
    pool = await get_pool(request)
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE memories
            SET status = 'forgotten',
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            memory_id,
        )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Memory not found")


@router.post("/feedback", status_code=204)
async def submit_feedback(feedback: FeedbackRequest, request: Request):
    if not feedback.success:
        return

    pool = await get_pool(request)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE memories
            SET success_count = success_count + 1,
                importance_boost = LEAST(1.0, importance_boost + $2),
                last_reinforced = NOW()
            WHERE id = $1::uuid
            """,
            feedback.memory_id,
            feedback.boost_amount,
        )
