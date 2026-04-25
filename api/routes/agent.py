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
    is_test: bool = Field(default=False)


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
    from src.models import MemoryNode, MemoryKind, MemorySource
    from uuid import UUID

    store = request.app.state.store
    provider = request.app.state.provider
    integrity = request.app.state.integrity

    # 1. Generate Embedding
    embedding = await provider.get_embedding(payload.content) if payload.with_embedding else None
    
    # 2. Create Node
    new_node = MemoryNode(
        content=payload.content,
        persona=payload.persona,
        importance=payload.importance,
        concept_tags=payload.tags,
        session_id=UUID(payload.session_id) if payload.session_id else None,
        source_type=MemorySource(payload.source_type),
        memory_kind=MemoryKind(payload.memory_kind),
        confidence=payload.confidence,
        emotional_weight=payload.emotional_weight,
        embedding=embedding,
        is_test=payload.is_test
    )

    # 3. Persistence FIRST (to satisfy Foreign Key constraints for relations)
    await store.insert(new_node)

    # 4. CONFLICT DETECTION & RESOLUTION
    conflicts = []
    if not payload.is_test:
        conflicts = await integrity.detect_conflicts(new_node)
        if conflicts:
            await integrity.resolve_conflicts(new_node, conflicts)
            # Update the node again if resolve_conflicts modified its metadata/conflict_with
            await store.update(new_node)

    return {
        "ok": True,
        "conflict_detected": len(conflicts) if not payload.is_test else 0,
        "memory": {
            "id": str(new_node.id),
            "persona": new_node.persona,
            "content": new_node.content,
            "importance": new_node.importance,
            "tags": new_node.concept_tags,
            "source_type": new_node.source_type.value,
            "memory_kind": new_node.memory_kind.value,
            "confidence": new_node.confidence,
            "is_test": new_node.is_test,
            "conflict_with": str(new_node.conflict_with) if new_node.conflict_with else None,
            "created_at": new_node.created_at.isoformat(),
        },
    }


@router.post("/recall")
async def recall_memories(payload: RecallRequest, request: Request):
    import asyncio
    store = request.app.state.store
    provider = request.app.state.provider
    enhancer = request.app.state.enhancer

    # 1. Multi-Intent Routing (Query Decomposition)
    sub_queries = [payload.query]
    if len(payload.query) > 20 and ("?" in payload.query or "什麼" in payload.query or "然後" in payload.query):
        sub_queries = await enhancer.expand_query(payload.query)
        if not sub_queries:
            sub_queries = [payload.query]

    # 2. Parallel Search for all sub-queries
    async def _search_sub_query(sq: str):
        # Advanced Embedding Generation (HyDE)
        q_emb = await enhancer.generate_hyde_embedding(sq)
        if not q_emb:
            return []
        
        return await store.search(
            q_emb,
            limit=payload.limit,
            persona=payload.persona,
            min_similarity=payload.min_similarity
        )

    search_tasks = [_search_sub_query(sq) for sq in sub_queries]
    nested_results = await asyncio.gather(*search_tasks)

    # 3. Deduplicate and merge results
    unique_memories = {}  # memory_id -> (max_similarity, node)
    for results in nested_results:
        for similarity, node in results:
            if node.id not in unique_memories or similarity > unique_memories[node.id][0]:
                unique_memories[node.id] = (similarity, node)

    # 4. Sort and limit merged results
    merged_results = sorted(unique_memories.values(), key=lambda x: x[0], reverse=True)[:payload.limit]

    memories = []
    for similarity, node in merged_results:
        # 5. Dynamic Ranking (Cognitive Score)
        score = (
            similarity * 0.45
            + node.importance * 0.2
            + min(1.0, node.access_count / 10) * 0.1
            + min(1.0, node.success_count / 8) * 0.1
            + node.confidence * 0.1
            + node.emotional_weight * 0.05
        )
        
        memories.append({
            "id": str(node.id),
            "content": node.content,
            "persona": node.persona,
            "importance": node.importance,
            "tags": node.concept_tags,
            "access_count": node.access_count,
            "success_count": node.success_count,
            "confidence": node.confidence,
            "emotional_weight": node.emotional_weight,
            "source_type": node.source_type.value,
            "memory_kind": node.memory_kind.value,
            "created_at": node.created_at.isoformat(),
            "similarity": round(similarity, 4),
            "score": round(score, 4),
        })

    # 4. Update Access Stats
    if memories:
        for m_id in [UUID(m["id"]) for m in memories]:
            node = await store.get(m_id)
            if node:
                node.access()
                await store.update(node)

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
