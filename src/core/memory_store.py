"""PostgreSQL-backed memory store for the Cortex Memory Engine."""

from __future__ import annotations

import asyncpg
import json
from typing import Optional
from uuid import UUID

from ..models import (
    MemoryKind,
    MemoryNode,
    MemorySource,
    MemoryStatus,
    MemoryStoreConfig,
    ZoomLevel,
)


class MemoryStore:
    """Persist and query `MemoryNode` objects in PostgreSQL."""

    def __init__(self, config: MemoryStoreConfig):
        """Initialize the memory store with database configuration."""
        self.config = config
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish connection pool with PostgreSQL and register vector type."""
        async def setup(conn: asyncpg.Connection) -> None:
            await conn.set_type_codec(
                "vector",
                encoder=lambda v: str(v),
                decoder=lambda v: [float(x) for x in v[1:-1].split(",")],
                schema="public",
                format="text",
            )

        self._pool = await asyncpg.create_pool(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            min_size=2,
            max_size=self.config.pool_size,
            setup=setup,
        )

    async def disconnect(self) -> None:
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()

    async def init_schema(self) -> None:
        """Initialize the database schema, including tables and default indices."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS memories (
                    id UUID PRIMARY KEY,
                    content TEXT NOT NULL,
                    summary_l1 TEXT,
                    summary_l0 TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    importance FLOAT NOT NULL DEFAULT 0.5,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed TIMESTAMPTZ,
                    importance_boost FLOAT NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'active',
                    embedding vector({self.config.vector_dim}),
                    zoom_level TEXT NOT NULL DEFAULT 'l2',
                    sentiment TEXT,
                    session_id UUID,
                    persona TEXT NOT NULL DEFAULT 'default',
                    conflict_with UUID,
                    source_type TEXT NOT NULL DEFAULT 'user',
                    memory_kind TEXT NOT NULL DEFAULT 'episodic',
                    confidence FLOAT NOT NULL DEFAULT 0.7,
                    emotional_weight FLOAT NOT NULL DEFAULT 0.0,
                    concept_tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
                    success_count INTEGER NOT NULL DEFAULT 0,
                    consolidation_count INTEGER NOT NULL DEFAULT 0,
                    activation_score FLOAT NOT NULL DEFAULT 0.0,
                    last_reinforced TIMESTAMPTZ,
                    last_consolidated TIMESTAMPTZ,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_test BOOLEAN NOT NULL DEFAULT FALSE,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::JSONB
                )
                """
            )

            # Create Relationships table for Knowledge Graph
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_relations (
                    source_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    target_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    relation_type TEXT NOT NULL,
                    weight FLOAT NOT NULL DEFAULT 1.0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (source_id, target_id, relation_type)
                )
                """
            )

            # Migration statements for existing DBs
            for statement in (
                "ALTER TABLE memories ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE memories ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE",
                "ALTER TABLE memories ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::JSONB",
                "CREATE INDEX IF NOT EXISTS idx_memories_content_fts ON memories USING GIN(to_tsvector('simple', content))",
                "CREATE INDEX IF NOT EXISTS idx_memories_embedding_hnsw ON memories USING hnsw (embedding vector_cosine_ops)",
            ):
                await conn.execute(statement)

    async def insert(self, memory: MemoryNode) -> MemoryNode:
        """Insert a new `MemoryNode` into the database."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (
                    id, content, summary_l1, summary_l0, created_at, updated_at,
                    importance, access_count, last_accessed, importance_boost,
                    status, embedding, zoom_level, sentiment, session_id, persona,
                    conflict_with, source_type, memory_kind, confidence,
                    emotional_weight, concept_tags, success_count,
                    consolidation_count, activation_score, last_reinforced,
                    last_consolidated, version, is_test, metadata
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24,
                    $25, $26, $27, $28, $29, $30
                )
                """,
                memory.id,
                memory.content,
                memory.summary_l1,
                memory.summary_l0,
                memory.created_at,
                memory.updated_at,
                memory.importance,
                memory.access_count,
                memory.last_accessed,
                memory.importance_boost,
                memory.status.value,
                memory.embedding,
                memory.zoom_level.value,
                memory.sentiment,
                memory.session_id,
                memory.persona,
                memory.conflict_with,
                memory.source_type.value,
                memory.memory_kind.value,
                memory.confidence,
                memory.emotional_weight,
                memory.concept_tags,
                memory.success_count,
                memory.consolidation_count,
                memory.activation_score,
                memory.last_reinforced,
                memory.last_consolidated,
                memory.version,
                memory.is_test,
                json.dumps(memory.metadata),
            )
        return memory

    async def get(self, memory_id: UUID) -> Optional[MemoryNode]:
        """Fetch a specific memory node by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM memories WHERE id = $1", memory_id)
            return self._row_to_memory(row) if row else None

    async def update(self, memory: MemoryNode) -> MemoryNode:
        """Update an existing memory node in the database."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memories SET
                    content = $2,
                    summary_l1 = $3,
                    summary_l0 = $4,
                    updated_at = $5,
                    importance = $6,
                    access_count = $7,
                    last_accessed = $8,
                    importance_boost = $9,
                    status = $10,
                    embedding = $11,
                    zoom_level = $12,
                    sentiment = $13,
                    session_id = $14,
                    persona = $15,
                    conflict_with = $16,
                    source_type = $17,
                    memory_kind = $18,
                    confidence = $19,
                    emotional_weight = $20,
                    concept_tags = $21,
                    success_count = $22,
                    consolidation_count = $23,
                    activation_score = $24,
                    last_reinforced = $25,
                    last_consolidated = $26,
                    version = $27,
                    is_test = $28,
                    metadata = $29
                WHERE id = $1
                """,
                memory.id,
                memory.content,
                memory.summary_l1,
                memory.summary_l0,
                memory.updated_at,
                memory.importance,
                memory.access_count,
                memory.last_accessed,
                memory.importance_boost,
                memory.status.value,
                memory.embedding,
                memory.zoom_level.value,
                memory.sentiment,
                memory.session_id,
                memory.persona,
                memory.conflict_with,
                memory.source_type.value,
                memory.memory_kind.value,
                memory.confidence,
                memory.emotional_weight,
                memory.concept_tags,
                memory.success_count,
                memory.consolidation_count,
                memory.activation_score,
                memory.last_reinforced,
                memory.last_consolidated,
                memory.version,
                memory.is_test,
                json.dumps(memory.metadata),
            )
        return memory

    async def delete(self, memory_id: UUID) -> bool:
        """Permanently delete a memory node by ID."""
        async with self._pool.acquire() as conn:
            result = await conn.execute("DELETE FROM memories WHERE id = $1", memory_id)
            return "DELETE 1" in result

    async def mark_consolidated(self, memory_ids: list[UUID]) -> int:
        """Batch update memories to CONSOLIDATED status and reduce their importance."""
        if not memory_ids:
            return 0
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE memories SET
                    status = 'consolidated',
                    importance = importance * 0.5,
                    consolidation_count = consolidation_count + 1,
                    last_consolidated = NOW(),
                    updated_at = NOW()
                WHERE id = ANY($1::uuid[])
                """,
                memory_ids
            )
            return int(result.split(" ")[1]) if result.startswith("UPDATE") else 0

    async def add_relation(self, source_id: UUID, target_id: UUID, relation_type: str, weight: float = 1.0) -> None:
        """Add or update a directed relationship between two memory nodes."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_relations (source_id, target_id, relation_type, weight, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (source_id, target_id, relation_type) DO UPDATE SET weight = $4
                """,
                source_id,
                target_id,
                relation_type,
                weight,
            )

    async def delete_relation(self, source_id: UUID, target_id: UUID, relation_type: str) -> bool:
        """Remove a specific relationship from the Knowledge Graph."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM memory_relations WHERE source_id = $1 AND target_id = $2 AND relation_type = $3",
                source_id,
                target_id,
                relation_type,
            )
            return "DELETE 1" in result

    async def get_relations(self, memory_id: UUID, direction: str = "both") -> list[dict]:
        """Fetch all relationships for a specific node in the given direction."""
        async with self._pool.acquire() as conn:
            if direction == "out":
                rows = await conn.fetch("SELECT * FROM memory_relations WHERE source_id = $1", memory_id)
            elif direction == "in":
                rows = await conn.fetch("SELECT * FROM memory_relations WHERE target_id = $1", memory_id)
            else:
                rows = await conn.fetch("SELECT * FROM memory_relations WHERE source_id = $1 OR target_id = $1", memory_id)

            return [dict(row) for row in rows]

    async def search(
        self, 
        query_embedding: list[float], 
        limit: int = 10, 
        persona: str = "default",
        min_similarity: float = 0.0
    ) -> list[tuple[float, MemoryNode]]:
        """Perform vector similarity search and return results with scores."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *, 1 - (embedding <=> $1::vector) AS similarity
                FROM memories
                WHERE status != 'forgotten'
                  AND persona = $2
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> $1::vector) >= $3
                ORDER BY embedding <=> $1::vector
                LIMIT $4
                """,
                query_embedding,
                persona,
                min_similarity,
                limit
            )
            return [(float(row["similarity"]), self._row_to_memory(row)) for row in rows]

    async def list_all(self, status: Optional[str] = None, limit: int = 100) -> list[MemoryNode]:
        """List memory nodes, optionally filtered by status, ordered by activation score."""
        async with self._pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM memories
                    WHERE status = $1
                    ORDER BY activation_score DESC, updated_at DESC
                    LIMIT $2
                    """,
                    status,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM memories
                    ORDER BY activation_score DESC, updated_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            return [self._row_to_memory(row) for row in rows]

    async def list_by_session(self, session_id: UUID, limit: int = 100) -> list[MemoryNode]:
        """Retrieve all memory nodes associated with a specific session ID."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM memories
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                session_id,
                limit,
            )
            return [self._row_to_memory(row) for row in rows]

    async def list_by_persona(self, persona: str, limit: int = 100) -> list[MemoryNode]:
        """Retrieve all memory nodes belonging to a specific persona namespace."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM memories
                WHERE persona = $1
                ORDER BY activation_score DESC, updated_at DESC
                LIMIT $2
                """,
                persona,
                limit,
            )
            return [self._row_to_memory(row) for row in rows]

    async def list_by_concepts(self, tags: list[str], limit: int = 50) -> list[MemoryNode]:
        """Query memory nodes containing any of the provided concept tags."""
        if not tags:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM memories
                WHERE concept_tags && $1::TEXT[]
                ORDER BY activation_score DESC, updated_at DESC
                LIMIT $2
                """,
                tags,
                limit,
            )
            return [self._row_to_memory(row) for row in rows]

    async def get_stats(self) -> dict:
        """Generate comprehensive cognitive statistics about the memory store."""
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM memories")

            status_rows = await conn.fetch(
                "SELECT status, COUNT(*) as cnt FROM memories GROUP BY status"
            )
            status_counts = {row["status"]: row["cnt"] for row in status_rows}

            daily_rows = await conn.fetch(
                """
                SELECT DATE(created_at) as day, COUNT(*) as cnt
                FROM memories
                WHERE created_at >= NOW() - INTERVAL '14 days'
                GROUP BY DATE(created_at)
                ORDER BY day
                """
            )
            daily_trend = [
                {"day": row["day"].isoformat(), "count": row["cnt"]}
                for row in daily_rows
            ]

            top_rows = await conn.fetch(
                """
                SELECT id, summary_l1, summary_l0, access_count
                FROM memories
                ORDER BY access_count DESC, activation_score DESC
                LIMIT 5
                """
            )
            top_accessed = [
                {
                    "id": str(row["id"]),
                    "summary": row["summary_l1"] or row["summary_l0"] or "memory",
                    "access_count": row["access_count"],
                }
                for row in top_rows
            ]

            top_activation_rows = await conn.fetch(
                """
                SELECT id, summary_l1, summary_l0, activation_score
                FROM memories
                ORDER BY activation_score DESC, updated_at DESC
                LIMIT 5
                """
            )
            top_activated = [
                {
                    "id": str(row["id"]),
                    "summary": row["summary_l1"] or row["summary_l0"] or "memory",
                    "activation_score": round(float(row["activation_score"] or 0), 3),
                }
                for row in top_activation_rows
            ]

            avg_imp = await conn.fetchval("SELECT AVG(importance) FROM memories")
            avg_conf = await conn.fetchval("SELECT AVG(confidence) FROM memories")
            avg_emotional = await conn.fetchval(
                "SELECT AVG(emotional_weight) FROM memories"
            )
            avg_activation = await conn.fetchval(
                "SELECT AVG(activation_score) FROM memories"
            )

            sent_rows = await conn.fetch(
                """
                SELECT sentiment, COUNT(*) as cnt
                FROM memories
                WHERE sentiment IS NOT NULL
                GROUP BY sentiment
                """
            )
            sentiment_counts = {row["sentiment"]: row["cnt"] for row in sent_rows}

            persona_rows = await conn.fetch(
                "SELECT persona, COUNT(*) as cnt FROM memories GROUP BY persona"
            )
            persona_counts = {row["persona"]: row["cnt"] for row in persona_rows}

            source_rows = await conn.fetch(
                "SELECT source_type, COUNT(*) as cnt FROM memories GROUP BY source_type"
            )
            source_counts = {row["source_type"]: row["cnt"] for row in source_rows}

            kind_rows = await conn.fetch(
                "SELECT memory_kind, COUNT(*) as cnt FROM memories GROUP BY memory_kind"
            )
            memory_kind_counts = {
                row["memory_kind"]: row["cnt"] for row in kind_rows
            }

            session_rows = await conn.fetch(
                """
                SELECT session_id, MIN(created_at) as started, COUNT(*) as cnt
                FROM memories
                WHERE session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY started DESC
                LIMIT 50
                """
            )
            sessions = [
                {
                    "session_id": str(row["session_id"]),
                    "started": row["started"].isoformat(),
                    "count": row["cnt"],
                }
                for row in session_rows
            ]

            return {
                "total": total,
                "status_counts": status_counts,
                "daily_trend": daily_trend,
                "top_accessed": top_accessed,
                "top_activated": top_activated,
                "avg_importance": round(float(avg_imp or 0), 3),
                "avg_confidence": round(float(avg_conf or 0), 3),
                "avg_emotional_weight": round(float(avg_emotional or 0), 3),
                "avg_activation_score": round(float(avg_activation or 0), 3),
                "sentiment_counts": sentiment_counts,
                "persona_counts": persona_counts,
                "source_counts": source_counts,
                "memory_kind_counts": memory_kind_counts,
                "sessions": sessions,
            }

    def _row_to_memory(self, row: asyncpg.Record) -> MemoryNode:
        """Convert a database record (row) into a `MemoryNode` object."""
        return MemoryNode(
            id=row["id"],
            content=row["content"],
            summary_l1=row["summary_l1"],
            summary_l0=row["summary_l0"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            importance=row["importance"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            importance_boost=row["importance_boost"],
            status=MemoryStatus(row["status"]),
            embedding=row["embedding"],
            zoom_level=ZoomLevel(row["zoom_level"]),
            sentiment=row.get("sentiment"),
            session_id=row.get("session_id"),
            persona=row.get("persona", "default"),
            conflict_with=row.get("conflict_with"),
            source_type=MemorySource(row.get("source_type", "user")),
            memory_kind=MemoryKind(row.get("memory_kind", "episodic")),
            confidence=row.get("confidence", 0.7),
            emotional_weight=row.get("emotional_weight", 0.0),
            concept_tags=row.get("concept_tags") or [],
            success_count=row.get("success_count", 0),
            consolidation_count=row.get("consolidation_count", 0),
            activation_score=row.get("activation_score", 0.0),
            last_reinforced=row.get("last_reinforced"),
            last_consolidated=row.get("last_consolidated"),
            version=row.get("version", 1),
            is_test=row.get("is_test", False),
            metadata=json.loads(row.get("metadata", "{}")),
        )
