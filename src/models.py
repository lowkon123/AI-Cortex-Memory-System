"""Base Pydantic models for the Cortex Memory Engine."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class ZoomLevel(str, Enum):
    """Progressive depth levels for memory zoom."""

    L0_SUMMARY = "l0"  # Most compressed - broad overview
    L1_ABSTRACT = "l1"  # Medium compression - key points
    L2_FULL = "l2"  # Full memory - verbatim content


class MemoryStatus(str, Enum):
    """Operational status of a memory."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPRESSED = "compressed"
    FORGOTTEN = "forgotten"


class MemorySource(str, Enum):
    """How the memory entered the system."""

    USER = "user"
    SYSTEM = "system"
    INFERRED = "inferred"
    IMPORTED = "imported"


class MemoryKind(str, Enum):
    """The cognitive role of a memory."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    FACT = "fact"  # Structured facts extracted from raw inputs
    CONCEPT = "concept"  # Abstracted concepts or entity clusters


class RelationType(str, Enum):
    """Types of semantic relationships between memories."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    CAUSES = "causes"
    RELEVANT_TO = "relevant_to"
    PART_OF = "part_of"
    SUPERSEDES = "supersedes"  # For versioning (newer memory replaces older)


class MemoryRelation(BaseModel):
    """A directed edge in the Knowledge Graph tying two memories together."""

    source_id: UUID
    target_id: UUID
    relation_type: RelationType
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)


class MemoryNode(BaseModel):
    """A single memory node with hierarchical summarization support.

    Attributes:
        id: Unique identifier for the memory node.
        content: Raw content of the memory.
        summary_l1: Medium-compression summary (key points).
        summary_l0: High-compression summary (broad overview).
        created_at: Timestamp when the memory was created.
        updated_at: Timestamp when the memory was last modified.
        importance: Base importance score (0.0 to 1.0).
        access_count: Number of times this memory has been accessed.
        last_accessed: Timestamp of last access.
        importance_boost: Temporary boost from reinforcement feedback.
        status: Current operational status.
        embedding: Vector embedding for similarity search.
        zoom_level: Current zoom level for context injection.
        sentiment: Emotional polarity tag (positive/negative/neutral/mixed).
        session_id: Conversation session grouping identifier.
        persona: AI persona this memory belongs to.
        conflict_with: UUID of a contradicting memory, if any.
        source_type: Where the memory came from.
        memory_kind: Cognitive role in the memory system.
        confidence: How reliable the memory is.
        emotional_weight: Emotional salience of the memory.
        concept_tags: Extracted concepts/entities attached to the memory.
        success_count: Reinforcement count from successful recalls/tasks.
        consolidation_count: Number of sleep-cycle consolidations applied.
        activation_score: Cached dynamic activation score for recall.
        last_reinforced: Last time the memory was reinforced.
        last_consolidated: Last time the memory was consolidated.
        version: Integer version for conflict/update tracking.
        metadata: Schema-less extension for specialized agent data.
    """

    id: UUID = Field(default_factory=uuid4)
    content: str
    summary_l1: Optional[str] = None
    summary_l0: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    importance_boost: float = 0.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    embedding: Optional[list[float]] = None
    zoom_level: ZoomLevel = ZoomLevel.L2_FULL
    sentiment: Optional[str] = None
    session_id: Optional[UUID] = None
    persona: str = "default"
    conflict_with: Optional[UUID] = None
    source_type: MemorySource = MemorySource.USER
    memory_kind: MemoryKind = MemoryKind.EPISODIC
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    emotional_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    concept_tags: list[str] = Field(default_factory=list)
    success_count: int = 0
    consolidation_count: int = 0
    activation_score: float = 0.0
    last_reinforced: Optional[datetime] = None
    last_consolidated: Optional[datetime] = None
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)

    def access(self) -> None:
        """Record an access to this memory node."""
        self.access_count += 1
        self.last_accessed = utc_now()

    def boost(self, amount: float) -> None:
        """Apply a temporary importance boost (reinforcement feedback)."""
        self.importance_boost = max(self.importance_boost, amount)

    def reinforce(self, amount: float = 0.1) -> None:
        """Record successful use of the memory."""
        self.success_count += 1
        self.last_reinforced = utc_now()
        self.importance_boost = min(1.0, self.importance_boost + amount)

    def decay(self, factor: float) -> None:
        """Apply neural decay to importance and boost."""
        self.importance_boost *= factor
        if self.importance_boost < 0.01:
            self.importance_boost = 0.0

    def consolidate(self) -> None:
        """Mark one successful consolidation cycle."""
        self.consolidation_count += 1
        self.last_consolidated = utc_now()


class MemoryStoreConfig(BaseModel):
    """Configuration for the memory store."""

    host: str = "localhost"
    port: int = 5432
    database: str = "cortex_memory"
    user: str = "cortex_user"
    password: str = "cortex_pass"
    pool_size: int = 10
    vector_dim: int = 1024  # Default for bge-m3
