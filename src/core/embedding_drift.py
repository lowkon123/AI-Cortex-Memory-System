"""Embedding Drift Detector — Semantic drift detection and automatic re-embedding.

Fixes #19: As embedding models update, the vectors of old memories 
may experience "Semantic Drift," leading to inaccurate similarity calculations.

This module periodically samples old memories, calculates the cosine 
offset between new and old vectors, and triggers a batch re-embedding 
if the drift exceeds a specified threshold.
"""

from __future__ import annotations

import asyncio
import math
import random
from datetime import UTC, datetime, timedelta
from typing import Optional

import numpy as np

from ..models import MemoryNode, utc_now


class EmbeddingDriftDetector:
    """Detects and fixes embedding semantic drift in the memory store.

    Workflow:
    1. Sample N old memories.
    2. Recompute vectors using the current Embedding Provider.
    3. Compare new and old vectors using cosine distance (Drift Score).
    4. If average Drift > threshold, trigger full re-embedding.
    """

    def __init__(
        self,
        drift_threshold: float = 0.05,
        sample_size: int = 100,
        re_embed_batch_size: int = 50,
        check_interval_days: int = 7,
    ):
        """Initialize Drift Detector.

        Args:
            drift_threshold: Avg drift threshold (0.0–1.0) to trigger re-embedding.
                0.05 means 5% offset triggers it.
            sample_size: Number of memories to sample for detection.
            re_embed_batch_size: Batch size for re-embedding operations.
            check_interval_days: Days between automatic checks.
        """
        self.drift_threshold = drift_threshold
        self.sample_size = sample_size
        self.re_embed_batch_size = re_embed_batch_size
        self.check_interval_days = check_interval_days
        self._last_check: Optional[datetime] = None
        self._last_drift_score: float = 0.0
        self._total_re_embedded: int = 0

    def cosine_distance(self, v1: list[float], v2: list[float]) -> float:
        """Calculate cosine distance (1 - cosine_similarity) between two vectors.

        Higher distance means more drift. 0 = identical, 2 = exactly opposite.
        """
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 1.0
        similarity = float(np.dot(a / norm_a, b / norm_b))
        return 1.0 - max(-1.0, min(1.0, similarity))

    async def detect_drift(
        self,
        store,
        embedding_provider,
        sample_size: Optional[int] = None,
    ) -> dict:
        """Detect the degree of embedding drift in the store.

        Args:
            store: MemoryStore instance.
            embedding_provider: Current Embedding Provider.
            sample_size: Overwrites default sample size.

        Returns:
            Detection report with drift_score, drifted_count, etc.
        """
        n = sample_size or self.sample_size
        all_memories = await store.list_all(limit=n * 3)

        # Only sample memories that already have embeddings
        candidates = [m for m in all_memories if m.embedding is not None]
        if not candidates:
            return {"drift_score": 0.0, "drifted_count": 0, "sample_size": 0, "needs_re_embed": False}

        sample = random.sample(candidates, min(n, len(candidates)))

        drift_scores: list[float] = []
        drifted_nodes: list[MemoryNode] = []

        for memory in sample:
            try:
                new_embedding = await embedding_provider.get_embedding(memory.content)
                drift = self.cosine_distance(memory.embedding, new_embedding)
                drift_scores.append(drift)
                if drift > self.drift_threshold:
                    drifted_nodes.append(memory)
            except Exception:
                continue

        avg_drift = sum(drift_scores) / len(drift_scores) if drift_scores else 0.0
        self._last_drift_score = avg_drift
        self._last_check = utc_now()

        return {
            "drift_score": round(avg_drift, 4),
            "drifted_count": len(drifted_nodes),
            "sample_size": len(sample),
            "needs_re_embed": avg_drift > self.drift_threshold,
            "drifted_memory_ids": [str(m.id) for m in drifted_nodes],
            "checked_at": self._last_check.isoformat(),
        }

    async def re_embed_all(
        self,
        store,
        embedding_provider,
        dry_run: bool = False,
    ) -> dict:
        """Execute full re-embedding for the entire store.

        Args:
            store: MemoryStore instance.
            embedding_provider: Current Embedding Provider.
            dry_run: If True, calculates but does not update the database.

        Returns:
            Report with processed and updated counts.
        """
        all_memories = await store.list_all(limit=10000)
        candidates = [m for m in all_memories if m.embedding is not None]

        updated = 0
        errors = 0

        # Batch processing to avoid memory explosion
        for i in range(0, len(candidates), self.re_embed_batch_size):
            batch = candidates[i: i + self.re_embed_batch_size]
            for memory in batch:
                try:
                    new_embedding = await embedding_provider.get_embedding(memory.content)
                    if not dry_run:
                        memory.embedding = new_embedding
                        memory.updated_at = utc_now()
                        await store.update(memory)
                    updated += 1
                except Exception:
                    errors += 1
            # Brief pause between batches to prevent overwhelming the provider
            await asyncio.sleep(0.5)

        self._total_re_embedded += updated

        return {
            "total_candidates": len(candidates),
            "updated": updated,
            "errors": errors,
            "dry_run": dry_run,
        }

    async def re_embed_drifted(
        self,
        store,
        embedding_provider,
        memory_ids: list[str],
    ) -> dict:
        """Re-embed only specifically drifted memories (precision mode).

        Args:
            store: MemoryStore instance.
            embedding_provider: Current Embedding Provider.
            memory_ids: List of memory UUID strings to re-embed.

        Returns:
            Process report.
        """
        from uuid import UUID

        updated = 0
        errors = 0

        for id_str in memory_ids:
            try:
                memory = await store.get(UUID(id_str))
                if not memory:
                    continue
                new_embedding = await embedding_provider.get_embedding(memory.content)
                memory.embedding = new_embedding
                memory.updated_at = utc_now()
                await store.update(memory)
                updated += 1
            except Exception:
                errors += 1

        self._total_re_embedded += updated
        return {"updated": updated, "errors": errors}

    def should_check(self) -> bool:
        """Check if automatic scheduled detection is due."""
        if self._last_check is None:
            return True
        elapsed = utc_now() - self._last_check
        return elapsed >= timedelta(days=self.check_interval_days)

    def get_status(self) -> dict:
        """Fetch current status of the detector."""
        return {
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "last_drift_score": self._last_drift_score,
            "drift_threshold": self.drift_threshold,
            "total_re_embedded": self._total_re_embedded,
            "next_check_due": self.should_check(),
        }

    async def run_weekly_maintenance(
        self, store, embedding_provider, auto_fix: bool = True
    ) -> dict:
        """Weekly maintenance: Detect drift and optionally trigger precise re-embedding.

        Args:
            store: MemoryStore instance.
            embedding_provider: Embedding Provider.
            auto_fix: If True, automatically re-embeds detected drifted memories.

        Returns:
            Full maintenance report.
        """
        if not self.should_check():
            return {"skipped": True, "reason": "not_due_yet", **self.get_status()}

        report = await self.detect_drift(store, embedding_provider)

        if report["needs_re_embed"] and auto_fix:
            fix_report = await self.re_embed_drifted(
                store, embedding_provider, report["drifted_memory_ids"]
            )
            report["fix_report"] = fix_report

        return report
