-- Initialize Cortex Memory Database
-- Run on first database creation

-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create memories table
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    summary_l1 TEXT,
    summary_l0 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    importance REAL NOT NULL DEFAULT 0.5,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    importance_boost REAL NOT NULL DEFAULT 0.0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    embedding VECTOR(1024),
    zoom_level VARCHAR(5) NOT NULL DEFAULT 'l2',
    sentiment VARCHAR(20),
    session_id UUID,
    persona VARCHAR(100) NOT NULL DEFAULT 'default',
    conflict_with UUID,
    source_type VARCHAR(20) NOT NULL DEFAULT 'user',
    memory_kind VARCHAR(20) NOT NULL DEFAULT 'episodic',
    confidence REAL NOT NULL DEFAULT 0.7,
    emotional_weight REAL NOT NULL DEFAULT 0.0,
    concept_tags TEXT[] NOT NULL DEFAULT '{}',
    success_count INTEGER NOT NULL DEFAULT 0,
    consolidation_count INTEGER NOT NULL DEFAULT 0,
    activation_score REAL NOT NULL DEFAULT 0.0,
    last_reinforced TIMESTAMPTZ,
    last_consolidated TIMESTAMPTZ
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_memories_persona ON memories(persona);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING gin(concept_tags);
