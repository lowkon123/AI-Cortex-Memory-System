import requests
import json
import sys
from typing import List, Optional, Any
from mcp.server.fastmcp import FastMCP

# 初始化 MCP Server
# Cortex Memory Engine API 預設運行在 8002 埠
mcp = FastMCP("Cortex Memory Server")
API_BASE = "http://127.0.0.1:8002"

@mcp.tool()
def save_coding_memory(content: str, is_requirement: bool = False, is_commit: bool = False, importance: float = 0.5, persona: str = "antigravity") -> str:
    """
    Save a piece of coding memory (requirements, logic, code, or commits).
    Set is_requirement=True for high-priority user demands and specs.
    Set is_commit=True for code changes and snippets.
    """
    tags = []
    memory_kind = "episodic"
    
    if is_requirement:
        tags.append("coding_requirement")
        importance = 1.0
        memory_kind = "semantic"
    elif is_commit:
        tags.append("code_commit")
        importance = max(0.6, importance)
    else:
        tags.append("coding_general")

    payload = {
        "content": content,
        "importance": importance,
        "tags": tags,
        "memory_kind": memory_kind,
        "persona": persona,
        "source_type": "system",
        "confidence": 0.9 if is_requirement else 0.7
    }

    try:
        res = requests.post(f"{API_BASE}/agent/store", json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        return f"Successfully saved to Cortex. Memory ID: {data.get('memory', {}).get('id', 'Unknown')}"
    except Exception as e:
        return f"Failed to save coding memory: {str(e)}"

@mcp.tool()
def save_general_memory(content: str, persona: str = "antigravity", tags: Optional[List[str]] = None, importance: float = 0.5, memory_kind: str = "episodic") -> str:
    """
    Store any general information into the memory engine.
    - memory_kind: 'episodic' (chat turns, events) or 'semantic' (facts, rules).
    """
    payload = {
        "content": content,
        "persona": persona,
        "importance": importance,
        "tags": tags or [],
        "memory_kind": memory_kind,
        "source_type": "system"
    }
    try:
        res = requests.post(f"{API_BASE}/agent/store", json=payload, timeout=30)
        res.raise_for_status()
        return f"Memory stored successfully. ID: {res.json().get('memory', {}).get('id')}"
    except Exception as e:
        return f"Error storing memory: {str(e)}"

@mcp.tool()
def search_cortex_memory(query: str, persona: str = "antigravity", limit: int = 5) -> str:
    """
    Search the Cortex Memory Engine for relevant context via semantic similarity.
    Returns a prompt-ready context string.
    """
    payload = {
        "query": query,
        "persona": persona,
        "limit": limit,
        "system_prefix": "Relevant memories found for context:"
    }
    try:
        res = requests.post(f"{API_BASE}/agent/context", json=payload, timeout=30)
        res.raise_for_status()
        return res.json().get("context", "No context found.")
    except Exception as e:
        return f"Failed to search memories: {str(e)}"

@mcp.tool()
def recall_structured_memory(query: str, persona: str = "antigravity", limit: int = 5) -> str:
    """
    Search memories and return detailed JSON objects including similarity scores, IDs, and metadata.
    Use this when you need to specifically reinforce or update certain memory nodes.
    """
    payload = {
        "query": query,
        "persona": persona,
        "limit": limit
    }
    try:
        res = requests.post(f"{API_BASE}/agent/recall", json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        memories = data.get("memories", [])
        return json.dumps(memories, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error in structured recall: {str(e)}"

@mcp.tool()
def reinforce_memories(memory_ids: List[str], boost_amount: float = 0.1) -> str:
    """
    Strengthen specific memories that were useful. This increases their future retrieval priority.
    """
    payload = {
        "memory_ids": memory_ids,
        "boost_amount": boost_amount
    }
    try:
        res = requests.post(f"{API_BASE}/agent/reinforce", json=payload, timeout=30)
        res.raise_for_status()
        return f"Successfully reinforced {len(memory_ids)} memories."
    except Exception as e:
        return f"Failed to reinforce: {str(e)}"

@mcp.tool()
def update_memory(memory_id: str, content: Optional[str] = None, importance: Optional[float] = None, tags: Optional[List[str]] = None, summary_l1: Optional[str] = None, summary_l0: Optional[str] = None) -> str:
    """
    Update specific fields of an existing memory node.
    Use this to refine summaries, adjust importance, or add concept tags.
    """
    payload = {}
    if content is not None: payload["content"] = content
    if importance is not None: payload["importance"] = importance
    if tags is not None: payload["tags"] = tags
    if summary_l1 is not None: payload["summary_l1"] = summary_l1
    if summary_l0 is not None: payload["summary_l0"] = summary_l0

    if not payload:
        return "No fields provided for update."

    try:
        res = requests.patch(f"{API_BASE}/memories/{memory_id}", json=payload, timeout=30)
        res.raise_for_status()
        return f"Memory {memory_id} updated successfully."
    except Exception as e:
        return f"Error updating memory: {str(e)}"

@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """
    Soft-delete/forget a specific memory node by ID.
    """
    try:
        res = requests.delete(f"{API_BASE}/memories/{memory_id}", timeout=30)
        res.raise_for_status()
        return f"Memory {memory_id} has been forgotten."
    except Exception as e:
        return f"Error deleting memory: {str(e)}"

@mcp.tool()
def list_recent_memories(persona: str = "antigravity", limit: int = 10) -> str:
    """
    List the most recently added memories for a specific persona.
    """
    try:
        res = requests.get(f"{API_BASE}/memories/", params={"persona": persona, "limit": limit}, timeout=30)
        res.raise_for_status()
        return json.dumps(res.json(), indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error listing memories: {str(e)}"

@mcp.tool()
def get_engine_stats() -> str:
    """
    Retrieve statistics about the memory engine (total nodes, persona counts, etc).
    """
    try:
        res = requests.get(f"{API_BASE}/search/stats", timeout=30)
        res.raise_for_status()
        return json.dumps(res.json(), indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error getting stats: {str(e)}"

if __name__ == "__main__":
    # MCP stdio 模式下，stdout 只能輸出 JSON 格式的協定訊息
    # 任何 Log 應輸出至 stderr
    sys.stderr.write("Cortex MCP Server is starting...\n")
    mcp.run(transport="stdio")

