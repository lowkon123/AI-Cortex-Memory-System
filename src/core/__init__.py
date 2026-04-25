"""Cortex Memory Engine — Core Package.

Unified English-language implementation of the Cortex Memory Engine.
All modules in this package form the canonical source of truth.
"""

# Storage & Retrieval
from .memory_store import MemoryStore
from .memory_index import MemoryIndex
from .memory_ranker import MemoryRanker
from .memory_vector import MemoryVectorStore
from .embedding_provider import OllamaEmbeddingProvider

# Lifecycle & Maintenance
from .memory_forgetting import MemoryForgetting
from .memory_compressor import MemoryCompressor
from .memory_zoom import MemoryZoom
from .memory_summarizer import summarize
from .sleep_runner import run_sleep_cycle, get_last_sleep_report
from .index_maintenance import IndexMaintenance

# Intelligence & Extraction
from .fact_extractor import FactExtractionPipeline
from .conflict_detector import check_conflicts, batch_validate_low_confidence
from .proactive_scanner import scan_upcoming
from .knowledge_graph import KnowledgeGraph
from .query_reformer import QueryReformer

# Context Building
from .context_builder import ContextBuilder, InjectionPhase

# Cognitive Safeguards
from .session_guard import SessionGuard, get_guard
from .epistemic_marker import EpistemicMarker, EpistemicType
from .context_validator import ContextValidator
from .embedding_drift import EmbeddingDriftDetector
from .resource_manager import ResourceManager, get_resource_manager
from .memory_bypass import MemoryBypassPolicy, BypassMode, get_bypass_policy

# Analysis & Insights
from .timeline_snapshot import TimelineSnapshot
from .bias_detector import BiasDetector, BiasReport

__all__ = [
    # Storage
    "MemoryStore", "MemoryIndex", "MemoryRanker", "MemoryVectorStore",
    "OllamaEmbeddingProvider",
    # Lifecycle
    "MemoryForgetting", "MemoryCompressor", "MemoryZoom", "summarize",
    "run_sleep_cycle", "get_last_sleep_report", "IndexMaintenance",
    # Intelligence
    "FactExtractionPipeline", "check_conflicts", "batch_validate_low_confidence",
    "scan_upcoming", "KnowledgeGraph", "QueryReformer",
    # Context
    "ContextBuilder", "InjectionPhase",
    # Safeguards
    "SessionGuard", "get_guard",
    "EpistemicMarker", "EpistemicType",
    "ContextValidator",
    "EmbeddingDriftDetector",
    "ResourceManager", "get_resource_manager",
    "MemoryBypassPolicy", "BypassMode", "get_bypass_policy",
    # Analysis
    "TimelineSnapshot",
    "BiasDetector", "BiasReport",
]
