"""Integrity and Fact-checking engine for Cortex Memory.
Detects contradictions and manages conflict resolution.
"""

import json
import httpx
from typing import List, Optional, Tuple
from uuid import UUID
from src.models import MemoryNode, MemoryStatus, utc_now

class IntegrityEngine:
    def __init__(self, store, provider, model: str = "gemma4:e2b"):
        self.store = store
        self.provider = provider
        self.model = model
        self.base_url = "http://localhost:11434"

    async def detect_conflicts(self, new_node: MemoryNode) -> List[UUID]:
        """Search for memories that might contradict the new node."""
        if not new_node.embedding:
            return []
            
        # 1. Semantic search for candidates
        candidates = await self.store.search(
            new_node.embedding, 
            limit=5, 
            persona=new_node.persona,
            min_similarity=0.7  # Use threshold at store level for efficiency
        )
        
        conflicts = []
        for score, existing in candidates:
            if str(existing.id) != str(new_node.id):
                # 2. LLM Logical Check
                if await self._check_logical_contradiction(new_node.content, existing.content):
                    conflicts.append(existing.id)
        
        return conflicts

    async def _check_logical_contradiction(self, content_a: str, content_b: str) -> bool:
        """Ask LLM if two pieces of information are contradictory."""
        prompt = f"""You are a Fact-Checking Agent. Analyze if the following two instructions/facts are mutually exclusive or contradictory in a project context.

Fact A: {content_a}
Fact B: {content_b}

Do they contradict? (e.g., specifying different languages for the same role, conflicting architectural rules). 
Answer true only if they cannot BOTH be true at the same time.

Return ONLY a JSON object: {{"contradicts": true/false, "reason": "why"}}"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=30.0
                )
                full_json = response.json()
                if "response" not in full_json:
                    return False
                    
                raw_text = full_json["response"].strip()
                
                # Parse JSON from LLM response
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "{" in raw_text:
                    raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}")+1]
                
                data = json.loads(raw_text)
                return data.get("contradicts", False)
        except Exception:
            return False

    async def resolve_conflicts(self, new_node: MemoryNode, conflict_ids: List[UUID]):
        """Mark existing nodes as conflicted or superseded and link them."""
        for c_id in conflict_ids:
            existing = await self.store.get(c_id)
            if existing:
                # 1. Update status and conflict markers
                existing.status = MemoryStatus.ARCHIVED
                existing.conflict_with = new_node.id
                existing.metadata["superseded_by"] = str(new_node.id)
                await self.store.update(existing)
                
                # 2. Add explicit relation in the Knowledge Graph
                await self.store.add_relation(
                    source_id=new_node.id,
                    target_id=existing.id,
                    relation_type="SUPERSEDES",
                    weight=1.0
                )
                
                # Link the new one back in node memory
                new_node.conflict_with = existing.id
                new_node.metadata["supersedes"] = str(existing.id)
