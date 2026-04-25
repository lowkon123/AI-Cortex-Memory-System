from datetime import datetime, timedelta

from src.models import MemoryKind, MemoryNode
from src.core.context_builder import ContextBuilder
from src.core.memory_forgetting import MemoryForgetting
from src.core.memory_ranker import MemoryRanker


def test_ranker_prefers_reinforced_matching_memory():
    ranker = MemoryRanker()
    hot = MemoryNode(
        content="Launch planning memory",
        importance=0.8,
        confidence=0.9,
        emotional_weight=0.6,
        success_count=5,
        persona="planner",
        memory_kind=MemoryKind.WORKING,
        concept_tags=["launch", "roadmap"],
        last_accessed=datetime.utcnow(),
    )
    cold = MemoryNode(
        content="Old unrelated note",
        importance=0.3,
        confidence=0.4,
        persona="archive",
        memory_kind=MemoryKind.SEMANTIC,
        concept_tags=["random"],
        last_accessed=datetime.utcnow() - timedelta(days=30),
    )

    ranked = ranker.rank_memories(
        [cold, hot],
        persona="planner",
        query_tags=["launch"],
        desired_kinds=[MemoryKind.WORKING],
    )

    assert ranked[0][0] is hot
    assert hot.activation_score > cold.activation_score


def test_ranker_explanation_contains_reason():
    ranker = MemoryRanker()
    memory = MemoryNode(
        content="Important project memory",
        importance=0.9,
        confidence=0.95,
        concept_tags=["project"],
        persona="builder",
    )

    explanation = ranker.explain_score(memory, persona="builder", query_tags=["project"])

    assert explanation["score"] > 0
    assert explanation["reason"]
    assert "concept_tags" in explanation


def test_forgetting_can_compress_and_archive():
    forgetting = MemoryForgetting(stale_days=7)
    memory = MemoryNode(
        content="A" * 300,
        summary_l0="short",
        summary_l1="medium",
        access_count=3,
        importance=0.8,
        updated_at=datetime.utcnow() - timedelta(days=10),
        last_accessed=datetime.utcnow() - timedelta(days=10),
    )

    processed = forgetting.process_batch([memory])[0]

    assert processed.consolidation_count >= 1
    assert processed.status.value in {"compressed", "archived", "active"}


def test_context_builder_uses_zoom_and_budget():
    builder = ContextBuilder(max_tokens=200, encoding="cl100k_base")
    memory = MemoryNode(
        content="full " * 120,
        summary_l1="abstract summary",
        summary_l0="tiny summary",
        activation_score=0.3,
        confidence=0.8,
        concept_tags=["tiny"],
    )

    context = builder.build_context_with_zoom([(memory, 0.3)])

    assert "tiny summary" in context
    assert "score=" in context
