"""Cortex 2.0 知識萃取流水線。

此模組將原始對話內容轉化為結構化的事實 (Facts) 與事件 (Episodes)，
並支援版本控制與關聯檢測。
"""

import json
import httpx
from typing import Any, Optional
from uuid import UUID

from ..models import MemoryNode, MemoryKind, MemorySource, MemoryStatus


class FactExtractionPipeline:
    """從原始數據中提取結構化知識的流水線。"""

    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def extract_structured_knowledge(self, content: str) -> list[dict[str, Any]]:
        """從內容中提取事實、實體與關係。"""
        prompt = f"""請分析以下對話內容，提取其中的結構化知識。

提取目標：
1. **Fact (事實)**：持久性的資訊（如：使用者喜歡 React, 使用者住在台北）。
2. **Episode (事件)**：特定時間點發生的行為（如：使用者正在調整資料庫索引, 使用者今天重灌了電腦）。
3. **Concept (概念)**：提到的重要實體或術語（如：pgvector, React, Docker）。

規則：
- 以 JSON 格式回傳陣列。每個物件包含：
  - "type": "fact" | "episode" | "concept"
  - "content": 簡短的描述
  - "importance": 重要性評分 (0.0 - 1.0)
  - "metadata": 結構化屬性（例如對於 Fact，可以是 {{"key": "preference", "value": "React"}}）
  - "supersedes": 如果此事實可能推翻之前的某些舊知識，請說明（可選）

對話內容：
{content}

請直接回傳 JSON 陣列："""

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=120.0,
                )
                response.raise_for_status()
                raw = response.json()["response"].strip()

                if raw.startswith("```"):
                    lines = raw.split("\n")
                    lines = [l for l in lines if not l.startswith("```")]
                    raw = "\n".join(lines).strip()

                items = json.loads(raw)
                if not isinstance(items, list):
                    return []
                return items
            except Exception:
                return []

    def create_node_from_extracted(self, item: dict[str, Any], session_id: Optional[UUID] = None) -> MemoryNode:
        """將提取的項目轉化為 MemoryNode 對象。"""
        kind_map = {
            "fact": MemoryKind.FACT,
            "episode": MemoryKind.EPISODIC,
            "concept": MemoryKind.CONCEPT
        }
        
        kind = kind_map.get(item.get("type", "fact"), MemoryKind.FACT)
        
        return MemoryNode(
            content=item["content"],
            importance=item.get("importance", 0.5),
            memory_kind=kind,
            source_type=MemorySource.INFERRED,
            session_id=session_id,
            metadata=item.get("metadata", {}),
            status=MemoryStatus.ACTIVE
        )
