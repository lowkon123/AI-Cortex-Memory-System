"""Memory Bypass Policy — Reasoning-priority mode.

Fixes #47: Prevents the AI from over-relying on memory queries and 
becoming a "dictionary machine."

Certain query types naturally do not require memory support (math 
derivation, logical hypothesis analysis). Forcing memory queries in 
these cases wastes time and may introduce incorrect historical biases.

This module provides:
1. Rule-based Bypass judgment (Fast)
2. Configurable Exemption List (User-defined)
3. Hybrid Mode (Reasoning priority, memory as aid)
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class BypassMode(str, Enum):
    """Bypass modes for memory queries."""

    FULL = "full"
    """Complete bypass. Pure reasoning mode."""

    SOFT = "soft"
    """Lower priority for memory. Reasoning focused, memory as aid."""

    NONE = "none"
    """Normal mode. Full use of the memory system."""


class MemoryBypassPolicy:
    """Strategy layer deciding whether to bypass memory for pure reasoning.

    Design Philosophy:
        Memory is the AI's "long-term background," but not the "only 
        source of thought." For math, logic, and creative generation, 
        re-reasoning is often more accurate than citing from memory.
    """

    # Patterns triggering Full Bypass
    FULL_BYPASS_PATTERNS: list[str] = [
        r"calculate.{0,20}[0-9]",           # Calculations with numbers
        r"[0-9]+\s*[\+\-\*\/\^]\s*[0-9]+",  # Math expressions
        r"derive|prove|solve equation",     # Math derivation
        r"assume.{0,10}if",                 # Counter-factual assumptions
        r"if.{0,20}what would happen",      # Hypothetical thinking
        r"use.*algorithm.*solve",           # Algorithm analysis
    ]

    # Patterns triggering Soft Bypass (some memory reference preserved)
    SOFT_BYPASS_PATTERNS: list[str] = [
        r"imagine|creative|design a",       # Creative generation
        r"write me.*story|write a",         # Creative writing
        r"compare.*pros and cons",           # Comparison (memory as base)
        r"explain.*concept|what is",        # Concept explanation (memory as supplement)
        r"logically.*should",               # Logical reasoning (memory as backup)
    ]

    def __init__(
        self,
        full_bypass_patterns: Optional[list[str]] = None,
        soft_bypass_patterns: Optional[list[str]] = None,
        custom_full_terms: Optional[list[str]] = None,
        custom_soft_terms: Optional[list[str]] = None,
        enabled: bool = True,
    ):
        """Initialize Bypass Policy.

        Args:
            full_bypass_patterns: Overwrites default Full Bypass regex list.
            soft_bypass_patterns: Overwrites default Soft Bypass regex list.
            custom_full_terms: Additional Full Bypass keywords (string matching).
            custom_soft_terms: Additional Soft Bypass keywords (string matching).
            enabled: Whether the policy is enabled.
        """
        self._full_patterns = [
            re.compile(p, re.IGNORECASE) for p in (full_bypass_patterns or self.FULL_BYPASS_PATTERNS)
        ]
        self._soft_patterns = [
            re.compile(p, re.IGNORECASE) for p in (soft_bypass_patterns or self.SOFT_BYPASS_PATTERNS)
        ]
        self._custom_full: list[str] = custom_full_terms or []
        self._custom_soft: list[str] = custom_soft_terms or []
        self.enabled = enabled

        # Statistics
        self._bypass_counts: dict[str, int] = {
            BypassMode.FULL: 0,
            BypassMode.SOFT: 0,
            BypassMode.NONE: 0,
        }

    def evaluate(self, query: str) -> BypassMode:
        """Evaluate which bypass mode to use for a query.

        Args:
            query: User's input query.

        Returns:
            BypassMode: FULL / SOFT / NONE
        """
        if not self.enabled:
            return BypassMode.NONE

        # Check Full Bypass first
        if self._matches_full(query):
            self._bypass_counts[BypassMode.FULL] += 1
            return BypassMode.FULL

        # Check Soft Bypass next
        if self._matches_soft(query):
            self._bypass_counts[BypassMode.SOFT] += 1
            return BypassMode.SOFT

        self._bypass_counts[BypassMode.NONE] += 1
        return BypassMode.NONE

    def should_bypass(self, query: str) -> bool:
        """Quick check: should memory be completely bypassed?"""
        return self.evaluate(query) == BypassMode.FULL

    def get_memory_weight(self, query: str) -> float:
        """Get memory retrieval weight based on bypass mode.

        Returns:
            1.0 = Full weight (NONE mode)
            0.4 = Low weight aid (SOFT mode)
            0.0 = Ignore memory (FULL mode)
        """
        mode = self.evaluate(query)
        return {
            BypassMode.FULL: 0.0,
            BypassMode.SOFT: 0.4,
            BypassMode.NONE: 1.0,
        }[mode]

    def add_full_bypass_term(self, term: str) -> None:
        """Dynamically add Full Bypass keyword."""
        self._custom_full.append(term)

    def add_soft_bypass_term(self, term: str) -> None:
        """Dynamically add Soft Bypass keyword."""
        self._custom_soft.append(term)

    def get_stats(self) -> dict:
        """Fetch bypass trigger statistics."""
        total = sum(self._bypass_counts.values()) or 1
        return {
            "counts": dict(self._bypass_counts),
            "bypass_rate": round(
                (self._bypass_counts[BypassMode.FULL] + self._bypass_counts[BypassMode.SOFT])
                / total,
                3,
            ),
            "full_bypass_rate": round(self._bypass_counts[BypassMode.FULL] / total, 3),
        }

    def _matches_full(self, query: str) -> bool:
        """Check if Full Bypass is triggered."""
        for pattern in self._full_patterns:
            if pattern.search(query):
                return True
        query_lower = query.lower()
        return any(term.lower() in query_lower for term in self._custom_full)

    def _matches_soft(self, query: str) -> bool:
        """Check if Soft Bypass is triggered."""
        for pattern in self._soft_patterns:
            if pattern.search(query):
                return True
        query_lower = query.lower()
        return any(term.lower() in query_lower for term in self._custom_soft)


# Module-level default instance
_default_policy: Optional[MemoryBypassPolicy] = None


def get_bypass_policy() -> MemoryBypassPolicy:
    """Fetch default MemoryBypassPolicy instance."""
    global _default_policy
    if _default_policy is None:
        _default_policy = MemoryBypassPolicy()
    return _default_policy
