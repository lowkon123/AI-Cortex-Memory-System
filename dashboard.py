import os
import asyncio
import json
import sys
import io
import numpy as np
from datetime import datetime
from uuid import UUID, uuid4
from contextlib import asynccontextmanager


import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.memory_feedback import MemoryFeedback
from src.memory_graph import MemoryGraph
from src.models import MemoryKind, MemoryNode, MemorySource, MemoryStoreConfig, MemoryStatus, ZoomLevel, utc_now
from src.zh_tw.fact_extractor import FactExtractionPipeline
from src.zh_tw.memory_ranker import MemoryRanker
from src.zh_tw.memory_store import MemoryStore
from src.zh_tw.memory_zoom import MemoryZoom
from src.zh_tw.embedding_provider import OllamaEmbeddingProvider
from src.zh_tw.memory_summarizer import summarize
from src.zh_tw.sleep_runner import get_last_sleep_report, run_sleep_cycle

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

store = None
zoom = MemoryZoom()
provider = None
sleep_task = None
ranker = MemoryRanker()
feedback = MemoryFeedback()
memory_graph = MemoryGraph()
fact_pipeline = FactExtractionPipeline(model="bge-m3")


@asynccontextmanager
async def lifespan(app):
    global store, provider, sleep_task
    # 使用與 API Server 一致的連線設定
    store = MemoryStore(MemoryStoreConfig(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        user=os.getenv("DB_USER", "cortex_user"),
        password=os.getenv("DB_PASSWORD", "cortex_pass"),
        db=os.getenv("DB_NAME", "cortex_memory")
    ))
    await store.connect()

    await store.init_schema()
    provider = OllamaEmbeddingProvider(model="bge-m3")
    # 啟動背景睡眠循環 (2.3)
    sleep_task = asyncio.create_task(run_sleep_cycle(store, interval_hours=6))
    yield
    if sleep_task:
        sleep_task.cancel()
        try:
            await sleep_task
        except asyncio.CancelledError:
            pass
    if store:
        await store.disconnect()


app = FastAPI(title="Cortex Memory Dashboard", lifespan=lifespan)


def infer_emotional_weight(sentiment: str | None) -> float:
    mapping = {
        "positive": 0.55,
        "negative": 0.6,
        "mixed": 0.75,
        "neutral": 0.2,
        None: 0.2,
        "": 0.2,
    }
    return mapping.get(sentiment, 0.25)


async def enrich_memory(memory: MemoryNode, model: str = "bge-m3") -> MemoryNode:
    """Attach derived concepts and graph metadata to a memory."""
    if not memory.concept_tags:
        try:
            items = await fact_pipeline.extract_structured_knowledge(memory.content)
            facts = [item["content"] for item in items if item.get("type") == "fact"]
        except Exception:
            facts = []
        entities = memory_graph.extract_entities(memory.content)
        combined = []
        for item in facts + entities:
            text = str(item).strip()
            if text and text not in combined:
                combined.append(text)
        memory.concept_tags = combined[:10]

    memory_graph.add_memory(memory.id, entities=memory.concept_tags)
    return memory


def serialize_memory(memory: MemoryNode, include_reasoning: bool = False) -> dict:
    data = {
        "id": str(memory.id),
        "content": memory.content,
        "summary_l1": memory.summary_l1 or "",
        "summary_l0": memory.summary_l0 or "",
        "importance": memory.importance,
        "importance_boost": memory.importance_boost,
        "access_count": memory.access_count,
        "created_at": memory.created_at.isoformat() if memory.created_at else "",
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else "",
        "last_accessed": memory.last_accessed.isoformat() if memory.last_accessed else "",
        "status": memory.status.value,
        "zoom_level": memory.zoom_level.value,
        "sentiment": memory.sentiment or "",
        "session_id": str(memory.session_id) if memory.session_id else "",
        "persona": memory.persona,
        "conflict_with": str(memory.conflict_with) if memory.conflict_with else "",
        "source_type": memory.source_type.value,
        "memory_kind": memory.memory_kind.value,
        "confidence": memory.confidence,
        "emotional_weight": memory.emotional_weight,
        "concept_tags": memory.concept_tags,
        "success_count": memory.success_count,
        "consolidation_count": memory.consolidation_count,
        "activation_score": memory.activation_score,
        "last_reinforced": memory.last_reinforced.isoformat() if memory.last_reinforced else "",
        "last_consolidated": memory.last_consolidated.isoformat() if memory.last_consolidated else "",
        "version": memory.version,
        "metadata": memory.metadata,
    }
    if include_reasoning:
        data["recall"] = ranker.explain_score(memory)
    return data


# ═══════════════════════════════════════
#  API Endpoints
# ═══════════════════════════════════════

@app.get("/api/graph_data")
async def graph_data(session: str = None, persona: str = None):
    """提取所有記憶，計算向量相似度，組裝成 3D 節點圖 JSON（含群集著色）"""
    if session:
        memories = await store.list_by_session(UUID(session), limit=500)
    elif persona:
        memories = await store.list_by_persona(persona, limit=500)
    else:
        memories = await store.list_all(limit=500)

    nodes = []
    embeddings = []
    valid_ids = []

    for m in memories:
        recall = ranker.explain_score(m, persona=persona)
        m.activation_score = recall["score"]
        zoom.set_level(ZoomLevel.L1_ABSTRACT)
        label = zoom.get_content(m)
        if len(label) > 60:
            label = label[:57] + "..."

        zoom.set_level(ZoomLevel.L0_SUMMARY)
        group_label = zoom.get_content(m)

        node_data = serialize_memory(m)
        node_data.update({
            "label": label,
            "group": group_label,
            "boost": m.importance_boost,
            "cluster_id": 0,  # will be filled below
            "recall_reason": recall["reason"],
            "recall_breakdown": recall,
        })
        nodes.append(node_data)

        if m.embedding:
            embeddings.append(np.array(m.embedding, dtype=np.float32))
            valid_ids.append(str(m.id))
        else:
            embeddings.append(None)
            valid_ids.append(None)

    # K-Means 群集著色 (3.2)
    valid_embs = [e for e in embeddings if e is not None]
    cluster_map = {}
    if len(valid_embs) >= 2:
        try:
            from sklearn.cluster import KMeans
            k = min(6, len(valid_embs))
            X = np.array(valid_embs)
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(X)
            emb_idx = 0
            for i, emb in enumerate(embeddings):
                if emb is not None:
                    cluster_map[i] = int(labels[emb_idx])
                    emb_idx += 1
        except Exception:
            pass

    for i, node in enumerate(nodes):
        node["cluster_id"] = cluster_map.get(i, 0)

    # 大膽調降門檻 (0.45) 確保大部分相關節點都能連結，並增加視覺層次感
    links = []
    THRESHOLD = 0.45


    normed = []
    for emb in embeddings:
        if emb is not None:
            norm = np.linalg.norm(emb)
            normed.append(emb / norm if norm > 0 else emb)
        else:
            normed.append(None)

    for i in range(len(normed)):
        if normed[i] is None:
            continue
        for j in range(i + 1, len(normed)):
            if normed[j] is None:
                continue
            sim = float(np.dot(normed[i], normed[j]))
            if sim >= THRESHOLD:
                links.append({
                    "source": valid_ids[i],
                    "target": valid_ids[j],
                    "value": round(sim, 3),
                    "type": "similarity",
                })

    # 衝突連線 (2.2 visualization)
    conflict_ids = {str(m.id) for m in memories}
    for m in memories:
        if m.conflict_with and str(m.conflict_with) in conflict_ids:
            links.append({
                "source": str(m.id),
                "target": str(m.conflict_with),
                "value": 1.0,
                "type": "conflict",
            })

    return JSONResponse({"nodes": nodes, "links": links})


@app.get("/api/memory/{memory_id}")
async def get_memory(memory_id: str):
    """取得單一記憶的完整資料"""
    m = await store.get(UUID(memory_id))
    if not m:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(serialize_memory(m, include_reasoning=True))


@app.get("/api/memory/{memory_id}/explain")
async def explain_memory(memory_id: str):
    m = await store.get(UUID(memory_id))
    if not m:
        return JSONResponse({"error": "not found"}, status_code=404)
    explanation = ranker.explain_score(m, persona=m.persona, query_tags=m.concept_tags)
    return JSONResponse({"id": str(m.id), "explanation": explanation})


@app.post("/api/memory/{memory_id}/reinforce")
async def reinforce_memory(memory_id: str, request: Request):
    m = await store.get(UUID(memory_id))
    if not m:
        return JSONResponse({"error": "not found"}, status_code=404)
    body = await request.json()
    amount = float(body.get("amount", 0.1))
    feedback.reinforce_memory(m, amount)
    m.updated_at = utc_now()
    await store.update(m)
    return JSONResponse(
        {"ok": True, "success_count": m.success_count, "importance_boost": m.importance_boost}
    )


@app.patch("/api/memory/{memory_id}")
async def update_memory(memory_id: str, request: Request):
    """更新記憶欄位"""
    m = await store.get(UUID(memory_id))
    if not m:
        return JSONResponse({"error": "not found"}, status_code=404)
    
    body = await request.json()
    if "content" in body:
        m.content = body["content"]
    if "summary_l1" in body:
        m.summary_l1 = body["summary_l1"]
    if "summary_l0" in body:
        m.summary_l0 = body["summary_l0"]
    if "importance" in body:
        m.importance = float(body["importance"])
    if "importance_boost" in body:
        m.importance_boost = float(body["importance_boost"])
    if "status" in body:
        m.status = MemoryStatus(body["status"])
    if "persona" in body:
        m.persona = body["persona"]
    if "sentiment" in body:
        m.sentiment = body["sentiment"]
    if "confidence" in body:
        m.confidence = float(body["confidence"])
    if "emotional_weight" in body:
        m.emotional_weight = float(body["emotional_weight"])
    if "source_type" in body:
        m.source_type = MemorySource(body["source_type"])
    if "memory_kind" in body:
        m.memory_kind = MemoryKind(body["memory_kind"])
    if "concept_tags" in body:
        m.concept_tags = [str(tag).strip() for tag in body["concept_tags"] if str(tag).strip()]

    await enrich_memory(m)
    m.activation_score = ranker.score_memory(m, persona=m.persona, query_tags=m.concept_tags)
    m.updated_at = utc_now()
    await store.update(m)
    return JSONResponse({"ok": True})


@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """刪除記憶"""
    result = await store.delete(UUID(memory_id))
    return JSONResponse({"ok": result})


@app.post("/api/memory")
async def create_memory(request: Request):
    """手動新增記憶 (4.1)"""
    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    persona = body.get("persona", "default")
    importance = float(body.get("importance", 0.5))
    source_type = MemorySource(body.get("source_type", "user"))
    memory_kind = MemoryKind(body.get("memory_kind", "episodic"))
    confidence = float(body.get("confidence", 0.72))

    # 自動生成 embedding
    emb = await provider.get_embedding(content)

    # 自動生成摘要 + 情緒
    model = body.get("model", "gemma4:e2b")
    try:
        l1, l0, sentiment = await summarize(content, model)
    except Exception:
        l1 = content[:50] + "..."
        l0 = "手動"
        sentiment = "neutral"

    new_memory = MemoryNode(
        content=content,
        embedding=emb,
        importance=importance,
        summary_l1=l1,
        summary_l0=l0,
        sentiment=sentiment,
        persona=persona,
        source_type=source_type,
        memory_kind=memory_kind,
        confidence=confidence,
        emotional_weight=float(body.get("emotional_weight", infer_emotional_weight(sentiment))),
        concept_tags=[str(tag).strip() for tag in body.get("concept_tags", []) if str(tag).strip()],
    )
    await enrich_memory(new_memory, model=model)
    new_memory.activation_score = ranker.score_memory(
        new_memory,
        persona=new_memory.persona,
        query_tags=new_memory.concept_tags,
    )
    await store.insert(new_memory)
    return JSONResponse({"ok": True, "id": str(new_memory.id)})


@app.get("/api/stats")
async def get_stats():
    """記憶統計儀表板 (4.2)"""
    stats = await store.get_stats()
    return JSONResponse(stats)


@app.get("/api/sessions")
async def get_sessions():
    """取得所有 Session 列表"""
    stats = await store.get_stats()
    return JSONResponse({"sessions": stats.get("sessions", [])})


@app.get("/api/concepts/{tag}")
async def get_concept_memories(tag: str):
    memories = await store.list_by_concepts([tag], limit=100)
    return JSONResponse({"tag": tag, "memories": [serialize_memory(m) for m in memories]})


@app.get("/api/sleep_report")
async def sleep_report():
    return JSONResponse(get_last_sleep_report())


@app.get("/", response_class=HTMLResponse)
async def index():
    return DASHBOARD_HTML


@app.get("/timeline", response_class=HTMLResponse)
async def timeline_page():
    return TIMELINE_HTML

@app.get("/coding", response_class=HTMLResponse)
async def coding_page():
    return CODING_HTML


# ═══════════════════════════════════════
#  嵌入式前端 HTML/CSS/JS — 主 3D Dashboard
# ═══════════════════════════════════════

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cortex Memory Engine</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: 'Inter', sans-serif;
    background: #08080f;
    color: #d0d0e0;
    overflow: hidden;
    height: 100vh;
  }

  #graph-container { width: 100vw; height: 100vh; }

  /* ──── 頂部 ──── */
  #header {
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 28px;
    background: linear-gradient(180deg, rgba(8,8,15,0.96) 0%, rgba(8,8,15,0) 100%);
    pointer-events: none;
  }
  #header > * { pointer-events: auto; }

  #header h1 {
    font-size: 16px; font-weight: 700; letter-spacing: 3px;
    background: linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }

  #stats { display:flex; gap:18px; font-size:11px; color:#555; }
  #stats span { color:#60a5fa; font-weight:600; }

  /* ──── 控制列 ──── */
  #controls {
    position: fixed; top: 52px; left: 0; right: 0; z-index: 99;
    display: flex; align-items: center; gap: 10px;
    padding: 8px 28px;
    pointer-events: none;
  }
  #controls > * { pointer-events: auto; }

  .ctrl-btn {
    padding: 5px 14px; border-radius: 20px; font-size: 10px;
    font-family: 'Inter', sans-serif; cursor: pointer;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.04); color: #888;
    font-weight: 500; letter-spacing: 0.5px;
    transition: all 0.25s;
  }
  .ctrl-btn:hover { background: rgba(96,165,250,0.15); color: #60a5fa; border-color: rgba(96,165,250,0.3); }
  .ctrl-btn.active { background: rgba(96,165,250,0.2); color: #60a5fa; border-color: rgba(96,165,250,0.4); }

  .ctrl-select {
    padding: 5px 10px; border-radius: 20px; font-size: 10px;
    font-family: 'Inter', sans-serif; cursor: pointer;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.04); color: #888;
    appearance: none; outline: none;
  }

  .ctrl-divider { width:1px; height:20px; background:rgba(255,255,255,0.08); }

  /* ──── 右側面板 ──── */
  #panel {
    position: fixed; right: -520px; top: 0;
    width: 500px; height: 100vh;
    background: rgba(12, 12, 22, 0.97);
    border-left: 1px solid rgba(96, 165, 250, 0.1);
    backdrop-filter: blur(24px);
    transition: right 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 90;
    display: flex; flex-direction: column;
  }
  #panel.open { right: 0; }

  #panel-header {
    padding: 20px 24px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    display: flex; align-items: center; justify-content: space-between;
    flex-shrink: 0;
  }
  #panel-header h2 {
    font-size: 12px; text-transform: uppercase; letter-spacing: 3px; color: #60a5fa;
  }

  .panel-actions { display: flex; gap: 8px; }

  .btn {
    padding: 6px 14px; border-radius: 8px; font-size: 11px;
    font-family: 'Inter', sans-serif; cursor: pointer; border: none;
    font-weight: 500; letter-spacing: 0.5px;
    transition: all 0.2s;
  }
  .btn-save { background: rgba(96,165,250,0.15); color: #60a5fa; }
  .btn-save:hover { background: rgba(96,165,250,0.3); }
  .btn-delete { background: rgba(239,68,68,0.1); color: #ef4444; }
  .btn-delete:hover { background: rgba(239,68,68,0.25); }
  .btn-close { background: none; color: #555; border: 1px solid rgba(255,255,255,0.08); width:32px; height:32px; border-radius:8px; font-size:16px; display:flex; align-items:center; justify-content:center; }
  .btn-close:hover { color:#fff; background:rgba(255,255,255,0.05); }

  #panel-body {
    flex: 1; overflow-y: auto; padding: 20px 24px;
  }

  /* ──── 表單欄位樣式 ──── */
  .field { margin-bottom: 18px; }
  .field-label {
    font-size: 10px; text-transform: uppercase; letter-spacing: 2px;
    color: #555; margin-bottom: 6px; display:flex; align-items:center; gap:6px;
  }
  .field-label .badge {
    font-size: 9px; padding: 2px 6px; border-radius: 4px;
    background: rgba(167,139,250,0.15); color: #a78bfa;
  }

  .field textarea, .field input[type=text], .field input[type=number] {
    width: 100%; padding: 10px 14px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    color: #d0d0e0; font-size: 13px; font-family: 'Inter', sans-serif;
    outline: none; resize: vertical;
    transition: border-color 0.2s;
  }
  .field textarea:focus, .field input:focus {
    border-color: rgba(96,165,250,0.4);
  }
  .field textarea { min-height: 80px; line-height: 1.6; }
  .field-content textarea { min-height: 140px; }

  .field select {
    width: 100%; padding: 10px 14px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; color: #d0d0e0; font-size: 13px;
    font-family: 'Inter', sans-serif; outline: none;
    appearance: none; cursor: pointer;
  }

  /* ──── Meta Grid (唯讀資訊) ──── */
  .meta-row {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;
    margin-bottom: 18px;
  }
  .meta-cell {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px; padding: 10px 12px;
  }
  .meta-cell .mc-label { font-size:9px; text-transform:uppercase; letter-spacing:1.5px; color:#444; margin-bottom:4px; }
  .meta-cell .mc-value { font-size:13px; font-weight:600; }
  .mc-value.imp { color:#fbbf24; }
  .mc-value.acc { color:#34d399; }
  .mc-value.time { color:#a78bfa; font-size:11px; font-weight:400; }

  /* ──── Toast ──── */
  #toast {
    position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
    padding: 10px 24px; border-radius: 10px;
    background: rgba(34,197,94,0.2); border: 1px solid rgba(34,197,94,0.3);
    color: #22c55e; font-size: 13px; font-weight: 500;
    opacity: 0; transition: opacity 0.3s;
    z-index: 200; pointer-events: none;
  }
  #toast.show { opacity: 1; }

  /* ──── 搜尋欄 ──── */
  #search-box { position:fixed; bottom:24px; left:50%; transform:translateX(-50%); z-index:100; }
  #search-input {
    width: 440px; padding: 11px 20px;
    background: rgba(12, 12, 22, 0.88);
    border: 1px solid rgba(96, 165, 250, 0.15);
    border-radius: 999px; color: #d0d0e0; font-size: 13px;
    font-family: 'Inter', sans-serif;
    backdrop-filter: blur(20px); outline: none;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  #search-input:focus {
    border-color: rgba(96,165,250,0.45);
    box-shadow: 0 0 24px rgba(96,165,250,0.08);
  }
  #search-input::placeholder { color:#444; }

  /* ──── 新增記憶 FAB ──── */
  #fab-add {
    position: fixed; bottom: 24px; right: 28px; z-index: 100;
    width: 48px; height: 48px; border-radius: 50%;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    border: none; color: #fff; font-size: 24px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 20px rgba(96,165,250,0.3);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  #fab-add:hover { transform: scale(1.1); box-shadow: 0 6px 28px rgba(96,165,250,0.45); }

  /* ──── 新增記憶 Modal ──── */
  #add-modal {
    position: fixed; inset: 0; z-index: 150;
    background: rgba(0,0,0,0.7); backdrop-filter: blur(8px);
    display: none; align-items: center; justify-content: center;
  }
  #add-modal.show { display: flex; }
  #add-modal-inner {
    width: 480px; max-height: 80vh;
    background: rgba(16,16,28,0.98); border: 1px solid rgba(96,165,250,0.15);
    border-radius: 16px; padding: 28px; overflow-y: auto;
  }
  #add-modal-inner h3 {
    font-size: 14px; font-weight: 600; letter-spacing: 2px; color: #60a5fa;
    margin-bottom: 20px; text-transform: uppercase;
  }

  /* ──── 統計面板 ──── */
  #stats-panel {
    position: fixed; left: -380px; top: 0;
    width: 360px; height: 100vh;
    background: rgba(12, 12, 22, 0.97);
    border-right: 1px solid rgba(96, 165, 250, 0.1);
    backdrop-filter: blur(24px);
    transition: left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 90; overflow-y: auto;
    padding: 20px 24px;
  }
  #stats-panel.open { left: 0; }
  #stats-panel h2 {
    font-size: 12px; text-transform: uppercase; letter-spacing: 3px; color: #60a5fa;
    margin-bottom: 20px;
  }
  .stat-card {
    background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 16px; margin-bottom: 14px;
  }
  .stat-card h4 {
    font-size: 10px; text-transform: uppercase; letter-spacing: 2px; color: #555;
    margin-bottom: 10px;
  }
  .stat-big { font-size: 32px; font-weight: 700; }
  .stat-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .stat-bar-label { font-size: 11px; color: #888; width: 70px; }
  .stat-bar { flex:1; height:6px; border-radius:3px; background:rgba(255,255,255,0.05); overflow:hidden; }
  .stat-bar-fill { height:100%; border-radius:3px; transition: width 0.5s ease; }
  .stat-list-item { font-size: 12px; color: #999; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.03); }
  .stat-list-item span { color: #60a5fa; font-weight: 600; }

  /* 滾動條 */
  #panel-body::-webkit-scrollbar, #stats-panel::-webkit-scrollbar { width: 4px; }
  #panel-body::-webkit-scrollbar-track, #stats-panel::-webkit-scrollbar-track { background: transparent; }
  #panel-body::-webkit-scrollbar-thumb, #stats-panel::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 4px; }

  /* ──── 記憶清單 ──── */
  #list-panel {
    position: fixed; left: -380px; top: 0;
    width: 360px; height: 100vh;
    background: rgba(12, 12, 22, 0.97);
    border-right: 1px solid rgba(96, 165, 250, 0.1);
    backdrop-filter: blur(24px);
    transition: left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 90; overflow-y: auto;
    padding: 20px 24px;
    display: flex; flex-direction: column;
  }
  #list-panel.open { left: 0; }
  .list-item { 
    padding: 12px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); 
    border-radius: 8px; margin-bottom: 8px; cursor: pointer; transition: background 0.2s;
  }
  .list-item:hover { background: rgba(96,165,250,0.1); border-color: rgba(96,165,250,0.3); }
  #list-panel::-webkit-scrollbar { width: 4px; }
  #list-panel::-webkit-scrollbar-track { background: transparent; }
  #list-panel::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 4px; }
</style>
</head>
<body>

<div id="header">
  <h1>CORTEX MEMORY ENGINE</h1>
  <div id="stats">
    Nodes: <span id="stat-nodes">0</span> &nbsp;|&nbsp;
    Links: <span id="stat-links">0</span> &nbsp;|&nbsp;
    Threshold: <span>0.75</span>
  </div>
</div>

<!-- ════ 控制列 ════ -->
<div id="controls">
  <button class="ctrl-btn active" id="color-importance" onclick="setColorMode('importance')">By Importance</button>
  <button class="ctrl-btn" id="color-cluster" onclick="setColorMode('cluster')">By Topic</button>
  <button class="ctrl-btn" id="color-sentiment" onclick="setColorMode('sentiment')">By Sentiment</button>
  <div class="ctrl-divider"></div>
  <select class="ctrl-select" id="session-filter" onchange="filterBySession(this.value)">
    <option value="">All Sessions</option>
  </select>
  <select class="ctrl-select" id="persona-filter" onchange="filterByPersona(this.value)">
    <option value="">All Personas</option>
  </select>
  <div class="ctrl-divider"></div>
  <button class="ctrl-btn" onclick="toggleStats()">📊 Stats</button>
  <button class="ctrl-btn" onclick="location.href='/timeline'">📅 Timeline</button>
  <button class="ctrl-btn" onclick="location.href='/coding'">💻 Coding</button>
  <button class="ctrl-btn" id="btn-edit-mode" onclick="toggleEditMode()" style="color: #f472b6; border-color: rgba(244,114,182,0.3)">📝 Edit Mode</button>
</div>

<div id="graph-container"></div>

<!-- ════ 右側詳情+編輯面板 ════ -->
<div id="panel">
  <div id="panel-header">
    <h2>Memory Details</h2>
    <div class="panel-actions">
      <button class="btn btn-save" onclick="saveMemory()">Save Changes</button>
      <button class="btn btn-delete" onclick="deleteMemory()">Delete</button>
      <button class="btn btn-close" onclick="closePanel()">✕</button>
    </div>
  </div>
  <div id="panel-body">

    <!-- 唯讀 Meta -->
    <div class="meta-row">
      <div class="meta-cell"><div class="mc-label">Created</div><div class="mc-value time" id="f-created">—</div></div>
      <div class="meta-cell"><div class="mc-label">Updated</div><div class="mc-value time" id="f-updated">—</div></div>
      <div class="meta-cell"><div class="mc-label">Last Accessed</div><div class="mc-value time" id="f-accessed">—</div></div>
    </div>
    <div class="meta-row">
      <div class="meta-cell"><div class="mc-label">Access Count</div><div class="mc-value acc" id="f-access-count">—</div></div>
      <div class="field" style="margin-bottom:0"><div class="field-label">Sentiment</div>
        <select id="f-sentiment">
          <option value="positive">Positive</option>
          <option value="negative">Negative</option>
          <option value="neutral">Neutral</option>
          <option value="mixed">Mixed</option>
        </select>
      </div>
      <div class="field" style="margin-bottom:0"><div class="field-label">Persona</div><input type="text" id="f-persona"></div>
    </div>
    <div class="meta-row">
      <div class="meta-cell"><div class="mc-label">Zoom Level</div><div class="mc-value" id="f-zoom" style="color:#60a5fa">—</div></div>
      <div class="meta-cell"><div class="mc-label">Cluster</div><div class="mc-value" id="f-cluster" style="color:#34d399">—</div></div>
      <div class="meta-cell"><div class="mc-label">Memory ID</div><div class="mc-value time" id="f-id" style="font-size:9px;word-break:break-all;">—</div></div>
    </div>

    <!-- 可編輯欄位 -->
    <div class="meta-row">
      <div class="meta-cell"><div class="mc-label">Activation</div><div class="mc-value" id="f-activation" style="color:#22d3ee">0.00</div></div>
      <div class="field" style="margin-bottom:0"><div class="field-label">Confidence</div><input type="number" id="f-confidence" min="0" max="1" step="0.05"></div>
      <div class="field" style="margin-bottom:0"><div class="field-label">Emotion W.</div><input type="number" id="f-emotional" min="0" max="1" step="0.05"></div>
    </div>
    <div class="meta-row">
      <div class="field" style="margin-bottom:0"><div class="field-label">Kind</div>
        <select id="f-kind">
          <option value="working">working</option>
          <option value="episodic" selected>episodic</option>
          <option value="semantic">semantic</option>
          <option value="procedural">procedural</option>
        </select>
      </div>
      <div class="field" style="margin-bottom:0"><div class="field-label">Source</div>
        <select id="f-source">
          <option value="user" selected>user</option>
          <option value="system">system</option>
          <option value="inferred">inferred</option>
          <option value="imported">imported</option>
        </select>
      </div>
      <div class="meta-cell"><div class="mc-label">Success</div><div class="mc-value" id="f-success" style="color:#34d399">0</div></div>
    </div>
    <div class="field">
      <div class="field-label">Concept Tags</div>
      <input type="text" id="f-concepts" placeholder="tag1, tag2, tag3">
    </div>

    <div class="field field-content">
      <div class="field-label">Full Content (L2) <span class="badge">Editable</span></div>
      <textarea id="f-content"></textarea>
    </div>

    <div class="field">
      <div class="field-label">Summary (L1) <span class="badge">Editable</span></div>
      <textarea id="f-summary-l1" style="min-height:50px"></textarea>
    </div>

    <div class="field">
      <div class="field-label">Glimpse (L0) <span class="badge">Editable</span></div>
      <input type="text" id="f-summary-l0">
    </div>

    <div class="meta-row" style="margin-top:4px">
      <div class="field" style="margin-bottom:0">
        <div class="field-label">Importance</div>
        <input type="number" id="f-importance" min="0" max="1" step="0.05">
      </div>
      <div class="field" style="margin-bottom:0">
        <div class="field-label">Reinforcement Boost</div>
        <input type="number" id="f-boost" min="0" max="1" step="0.05">
      </div>
      <div class="field" style="margin-bottom:0">
        <div class="field-label">Status</div>
        <select id="f-status">
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="compressed">Compressed</option>
          <option value="forgotten">Forgotten</option>
        </select>
      </div>
    </div>

  </div>
</div>

<!-- ════ Statistics Panel ════ -->
<div id="stats-panel">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
    <h2 style="margin-bottom:0">System Statistics</h2>
    <button class="btn btn-close" onclick="toggleStats()">✕</button>
  </div>
  <div id="stats-content"></div>
</div>

<!-- ════ Memory List ════ -->
<div id="list-panel">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-shrink:0;">
    <h2 style="margin-bottom:0; font-size: 14px; color: #f472b6; letter-spacing:2px; font-weight: 600;">Neural Memories</h2>
    <button class="btn btn-close" onclick="toggleEditMode()">✕</button>
  </div>
  <div id="list-content" style="flex:1; overflow-y:auto; padding-right: 5px;"></div>
</div>

<div id="toast"></div>

<!-- ════ Add Memory Modal ════ -->
<div id="add-modal">
  <div id="add-modal-inner">
    <h3>✨ New Memory</h3>
    <div class="field field-content">
      <div class="field-label">Memory Content</div>
      <textarea id="add-content" placeholder="Type something to remember..."></textarea>
    </div>
    <div class="meta-row">
      <div class="field" style="margin-bottom:0">
        <div class="field-label">Importance</div>
        <input type="number" id="add-importance" value="0.5" min="0" max="1" step="0.05">
      </div>
      <div class="field" style="margin-bottom:0">
        <div class="field-label">Persona</div>
        <input type="text" id="add-persona" value="default">
      </div>
    </div>
    <div style="display:flex;gap:10px;margin-top:16px;justify-content:flex-end;">
      <button class="btn" style="background:rgba(255,255,255,0.05);color:#888;" onclick="closeAddModal()">Cancel</button>
      <button class="btn btn-save" onclick="submitNewMemory()">Store Memory</button>
    </div>
  </div>
</div>

<button id="fab-add" onclick="openAddModal()" title="Add Memory">＋</button>

<div id="search-box">
  <input id="search-input" type="text" placeholder="Search memories...">
</div>

<script src="https://unpkg.com/3d-force-graph"></script>

<script>
const container = document.getElementById('graph-container');
const Graph = ForceGraph3D()(container);
let currentNodeId = null;
let colorMode = 'importance';
let graphDataCache = null;
let isEditMode = false;
let pendingNodeClick = null;
let pendingNodeClickTimer = null;
const NODE_DOUBLE_CLICK_MS = 360;

// 群集色盤
const CLUSTER_COLORS = [
  '#60a5fa', '#f472b6', '#34d399', '#fbbf24', '#a78bfa',
  '#fb923c', '#22d3ee', '#e879f9', '#4ade80', '#f43f5e'
];

const SENTIMENT_COLORS = {
  positive: '#34d399',
  negative: '#ef4444',
  neutral: '#6b7280',
  mixed: '#fbbf24',
  '': '#6b7280'
};

function impColor(v) {
  v = v || 0.5;
  return `hsl(${220 + v * 100}, ${60 + v * 30}%, ${55 + v * 20}%)`;
}

function getNodeColor(n) {
  if (n._highlighted) return '#ffffff';
  if (colorMode === 'cluster') return CLUSTER_COLORS[n.cluster_id % CLUSTER_COLORS.length];
  if (colorMode === 'sentiment') return SENTIMENT_COLORS[n.sentiment] || '#6b7280';
  return impColor(n.importance);
}

function setColorMode(mode) {
  colorMode = mode;
  document.querySelectorAll('#controls .ctrl-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('color-' + mode);
  if (btn) btn.classList.add('active');
  Graph.nodeColor(getNodeColor);
}

function fmtTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
}

function toast(msg, ok=true) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.background = ok ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)';
  el.style.borderColor = ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)';
  el.style.color = ok ? '#22c55e' : '#ef4444';
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2200);
}

function focusNode(node) {
  if (!node) return;
  const d = 250; // 增加特寫距離，防止鏡頭太靠近而看不到節點
  const dist = Math.hypot(node.x || 0, node.y || 0, node.z || 0) || 0.001;
  const ratio = 1 + d / dist;
  Graph.cameraPosition(
    { x: (node.x || 0) * ratio, y: (node.y || 0) * ratio, z: (node.z || 0) * ratio },
    node, 800
  );
}

function clearPendingNodeClick() {
  if (pendingNodeClickTimer) {
    clearTimeout(pendingNodeClickTimer);
    pendingNodeClickTimer = null;
  }
  pendingNodeClick = null;
}

// ──── 載入 3D 圖 ────
function loadGraph(session='', persona='') {
  let url = '/api/graph_data';
  const params = [];
  if (session) params.push('session=' + session);
  if (persona) params.push('persona=' + persona);
  if (params.length) url += '?' + params.join('&');

  fetch(url)
    .then(r => r.json())
    .then(data => {
      graphDataCache = data;
      document.getElementById('stat-nodes').textContent = data.nodes.length;
      document.getElementById('stat-links').textContent = data.links.length;

      Graph
        .graphData(data)
        .backgroundColor('#08080f')
        .showNavInfo(false)
        .nodeVal(n => 2 + (n.importance || 0.1) * 8)
        .nodeColor(getNodeColor)
        .nodeOpacity(0.9)
        .nodeLabel(node => {
          return `<div style="background: rgba(16, 16, 28, 0.95); padding: 12px 14px; border-radius: 8px; border: 1px solid rgba(96, 165, 250, 0.3); box-shadow: 0 4px 12px rgba(0,0,0,0.5); backdrop-filter: blur(10px); max-width: 260px; font-family: 'Inter', sans-serif;">
            <div style="color: #60a5fa; font-size: 11px; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; text-transform: uppercase;">
              ${node.summary_l0 || 'Unclassified'}
            </div>
            <div style="color: #e2e8f0; font-size: 13px; line-height: 1.5; margin-bottom: 8px;">
              ${(node.summary_l1 || node.content || '').substring(0, 80)}${(node.summary_l1 || node.content || '').length > 80 ? '...' : ''}
            </div>
            <div style="display: flex; gap: 10px; font-size: 10px; color: #94a3b8;">
              <span>重要性 <b style="color: #fbbf24">${node.importance || 0}</b></span>
              <span>情緒 <b style="color: ${node.sentiment==='positive'?'#34d399':node.sentiment==='negative'?'#ef4444':'#fbbf24'}">${node.sentiment || '無'}</b></span>
            </div>
            <div style="font-size: 10px; color: #64748b; margin-top: 8px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 6px;">
              💡 點擊節點開啟編輯與詳細內容
            </div>
          </div>`;
        })
        .linkColor(l => {
          if (l.type === 'conflict') return 'rgba(239, 68, 68, 0.7)';
          const opacity = 0.15 + Math.pow(l.value || 0, 3) * 0.75;
          return `rgba(96, 165, 250, ${opacity})`;
        })
        .linkWidth(l => {
          if (l.type === 'conflict') return 1.5;
          return 0.4 + Math.pow(l.value || 0, 2) * 2.8;
        })
        .linkLineDash(l => {
          if (l.type === 'conflict') return [4, 2];
          return null;
        })
        .linkOpacity(0.35)
        .linkDirectionalParticles(6)
        .linkDirectionalParticleWidth(3.0)
        .linkDirectionalParticleSpeed(0.015)
        .linkDirectionalParticleColor(l => (l.type === 'conflict' ? '#ff3333' : '#00ffff'))


        .onNodeHover(node => { container.style.cursor = node ? 'pointer' : 'default'; })
        .onNodeClick(node => {
          if (!node) return;
          focusNode(node);
          openPanel(node);
        })
        .onNodeRightClick(node => {
          if (!node) return;
          focusNode(node);
          openPanel(node);
        })
        .d3Force('charge').strength(-60);

      // 載入 Session 選單
      loadFilters(data);
      if (isEditMode) renderMemoryList();
    });
}

loadGraph();

function loadFilters(data) {
  fetch('/api/sessions').then(r=>r.json()).then(d => {
    const sel = document.getElementById('session-filter');
    sel.innerHTML = '<option value="">所有 Session</option>';
    (d.sessions || []).forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.session_id;
      opt.textContent = s.session_id.substring(0,8) + '... (' + s.count + ')';
      sel.appendChild(opt);
    });
  });

  // Personas
  const personas = [...new Set(data.nodes.map(n => n.persona).filter(Boolean))];
  const pSel = document.getElementById('persona-filter');
  pSel.innerHTML = '<option value="">All Personas</option>';
  personas.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    pSel.appendChild(opt);
  });
}

function filterBySession(val) {
  document.getElementById('persona-filter').value = '';
  loadGraph(val, '');
}
function filterByPersona(val) {
  document.getElementById('session-filter').value = '';
  loadGraph('', val);
}

// ──── Open Panel ────
async function openPanel(node) {
  currentNodeId = node.id;

  let detail = node;
  try {
    const res = await fetch(`/api/memory/${node.id}`);
    if (res.ok) {
      detail = { ...node, ...(await res.json()) };
    }
  } catch (err) {
    console.error('Failed to load memory detail', err);
  }

  if (currentNodeId !== node.id) return;

  document.getElementById('f-id').textContent = detail.id;
  document.getElementById('f-created').textContent = fmtTime(detail.created_at);
  document.getElementById('f-updated').textContent = fmtTime(detail.updated_at);
  document.getElementById('f-accessed').textContent = fmtTime(detail.last_accessed);
  document.getElementById('f-access-count').textContent = detail.access_count ?? 0;
  document.getElementById('f-zoom').textContent = (detail.zoom_level || '').toUpperCase();
  document.getElementById('f-sentiment').value = detail.sentiment || 'neutral';
  document.getElementById('f-persona').value = detail.persona || 'default';
  document.getElementById('f-cluster').textContent = '#' + (detail.cluster_id ?? 0);
  document.getElementById('f-activation').textContent = (detail.activation_score ?? 0).toFixed(2);
  document.getElementById('f-confidence').value = (detail.confidence ?? 0).toFixed(2);
  document.getElementById('f-emotional').value = (detail.emotional_weight ?? 0).toFixed(2);
  document.getElementById('f-kind').value = detail.memory_kind || 'episodic';
  document.getElementById('f-source').value = detail.source_type || 'user';
  document.getElementById('f-success').textContent = String(detail.success_count ?? 0);

  document.getElementById('f-content').value = detail.content || '';
  document.getElementById('f-summary-l1').value = detail.summary_l1 || '';
  document.getElementById('f-summary-l0').value = detail.summary_l0 || '';
  document.getElementById('f-importance').value = detail.importance ?? 0.5;
  document.getElementById('f-boost').value = detail.importance_boost ?? detail.boost ?? 0;
  document.getElementById('f-status').value = detail.status || 'active';
  document.getElementById('f-concepts').value = (detail.concept_tags || []).join(', ');

  document.getElementById('panel').classList.add('open');
}

function closePanel() {
  clearPendingNodeClick();
  document.getElementById('panel').classList.remove('open');
  currentNodeId = null;
}

// ──── Edit List Mode ────
function toggleEditMode() {
  isEditMode = !isEditMode;
  Graph.enableNodeDrag(!isEditMode);
  
  const btn = document.getElementById('btn-edit-mode');
  const listPanel = document.getElementById('list-panel');
  if (isEditMode) {
    btn.classList.add('active');
    btn.innerHTML = '📝 Exit Edit';
    listPanel.classList.add('open');
    if (document.getElementById('stats-panel').classList.contains('open')) toggleStats();
    renderMemoryList();
  } else {
    btn.classList.remove('active');
    btn.innerHTML = '📝 Edit Mode';
    listPanel.classList.remove('open');
    closePanel();
  }
}

function renderMemoryList() {
  const data = Graph.graphData();
  const el = document.getElementById('list-content');
  let html = '';
  const nodes = data.nodes.slice().sort((a,b) => (b.importance||0) - (a.importance||0));
  nodes.forEach(n => {
    html += `<div class="list-item" onclick="selectNodeById('${n.id}')">
      <div style="display:flex; justify-content:space-between; margin-bottom:4px">
        <strong style="color:#60a5fa; font-size:12px;">${n.summary_l0 || 'Unclassified'}</strong>
        <span style="font-size:10px; color:#888;">#${n.cluster_id || 0}</span>
      </div>
      <div style="font-size:11px;color:#bbb; line-height: 1.4">${n.summary_l1 || n.content.substring(0,30) + '...'}</div>
      <div style="font-size:9px;color:#555;margin-top:6px;">Imp: <span style="color:#fbbf24">${n.importance||0.5}</span> | ${n.persona||'default'}</div>
    </div>`;
  });
  el.innerHTML = html;
}

function selectNodeById(id) {
  const data = Graph.graphData();
  const node = data.nodes.find(n => n.id === id);
  if (node) {
    focusNode(node);
    openPanel(node);
  }
}

// ──── Save ────
async function saveMemory() {
  if (!currentNodeId) return;
  const body = {
    content: document.getElementById('f-content').value,
    summary_l1: document.getElementById('f-summary-l1').value,
    summary_l0: document.getElementById('f-summary-l0').value,
    importance: parseFloat(document.getElementById('f-importance').value),
    importance_boost: parseFloat(document.getElementById('f-boost').value),
    status: document.getElementById('f-status').value,
    sentiment: document.getElementById('f-sentiment').value,
    persona: document.getElementById('f-persona').value,
    confidence: parseFloat(document.getElementById('f-confidence').value),
    emotional_weight: parseFloat(document.getElementById('f-emotional').value),
    memory_kind: document.getElementById('f-kind').value,
    source_type: document.getElementById('f-source').value,
    concept_tags: document.getElementById('f-concepts').value.split(',').map(v => v.trim()).filter(Boolean),
  };

  const res = await fetch(`/api/memory/${currentNodeId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (res.ok) {
    toast('Memory updated');
    loadGraph(); 
  } else {
    toast('Update failed', false);
  }
}

// ──── Delete ────
async function deleteMemory() {
  if (!currentNodeId) return;
  if (!confirm('Are you sure you want to permanently delete this memory? This action cannot be undone.')) return;

  const res = await fetch(`/api/memory/${currentNodeId}`, { method: 'DELETE' });
  if (res.ok) {
    toast('Memory deleted');
    closePanel();
    loadGraph();
  } else {
    toast('Deletion failed', false);
  }
}

// ──── Search ────
document.getElementById('search-input').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  const data = Graph.graphData();
  data.nodes.forEach(n => {
    n._highlighted = q && (n.content.toLowerCase().includes(q) || n.label.toLowerCase().includes(q));
  });
  Graph.nodeColor(getNodeColor);
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closePanel();
    closeAddModal();
    if (document.getElementById('stats-panel').classList.contains('open')) toggleStats();
  }
});

// ──── Add Memory Modal ────
function openAddModal() {
  document.getElementById('add-modal').classList.add('show');
  document.getElementById('add-content').value = '';
  document.getElementById('add-importance').value = '0.5';
  document.getElementById('add-persona').value = 'default';
  document.getElementById('add-content').focus();
}
function closeAddModal() {
  document.getElementById('add-modal').classList.remove('show');
}
async function submitNewMemory() {
  const content = document.getElementById('add-content').value.trim();
  if (!content) { toast('Please enter memory content', false); return; }

  const body = {
    content,
    importance: parseFloat(document.getElementById('add-importance').value),
    persona: document.getElementById('add-persona').value.trim() || 'default',
  };

  toast('Creating memory...');
  const res = await fetch('/api/memory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (res.ok) {
    toast('Memory created!');
    closeAddModal();
    loadGraph();
  } else {
    toast('Creation failed', false);
  }
}

// ──── Stats ────
function toggleStats() {
  const panel = document.getElementById('stats-panel');
  panel.classList.toggle('open');
  if (panel.classList.contains('open')) loadStats();
}

async function loadStats() {
  const res = await fetch('/api/stats');
  const s = await res.json();
  const el = document.getElementById('stats-content');

  const statusColors = { active: '#34d399', archived: '#fbbf24', compressed: '#60a5fa', forgotten: '#ef4444' };
  const total = s.total || 1;

  let statusBars = '';
  for (const [st, cnt] of Object.entries(s.status_counts || {})) {
    const pct = Math.round(cnt / total * 100);
    statusBars += `<div class="stat-bar-row">
      <div class="stat-bar-label">${st}</div>
      <div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%;background:${statusColors[st]||'#888'}"></div></div>
      <div style="font-size:11px;color:#888;width:40px;text-align:right">${cnt}</div>
    </div>`;
  }

  let sentBars = '';
  for (const [st, cnt] of Object.entries(s.sentiment_counts || {})) {
    const pct = Math.round(cnt / total * 100);
    const sc = {'positive':'#34d399','negative':'#ef4444','neutral':'#6b7280','mixed':'#fbbf24'};
    sentBars += `<div class="stat-bar-row">
      <div class="stat-bar-label">${st}</div>
      <div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%;background:${sc[st]||'#888'}"></div></div>
      <div style="font-size:11px;color:#888;width:40px;text-align:right">${cnt}</div>
    </div>`;
  }

  let topList = '';
  (s.top_accessed || []).forEach(t => {
    topList += `<div class="stat-list-item"><span>${t.access_count}×</span> ${t.summary}</div>`;
  });

  let trendSvg = '';
  const trend = s.daily_trend || [];
  if (trend.length > 1) {
    const maxC = Math.max(...trend.map(t=>t.count), 1);
    const w = 310, h = 80;
    let path = '';
    trend.forEach((t, i) => {
      const x = (i / (trend.length - 1)) * w;
      const y = h - (t.count / maxC) * h;
      path += (i === 0 ? 'M' : 'L') + x + ',' + y + ' ';
    });
    trendSvg = `<svg width="${w}" height="${h}" style="margin-top:8px">
      <path d="${path}" fill="none" stroke="#60a5fa" stroke-width="2"/>
    </svg>`;
  }

  el.innerHTML = `
    <div class="stat-card">
      <h4>Total Memories</h4>
      <div class="stat-big" style="color:#60a5fa">${s.total}</div>
      <div style="font-size:11px;color:#555;margin-top:4px">Avg Importance: <span style="color:#fbbf24">${s.avg_importance}</span></div>
    </div>
    <div class="stat-card"><h4>Status Distribution</h4>${statusBars}</div>
    <div class="stat-card"><h4>Sentiment Distribution</h4>${sentBars || '<div style="font-size:11px;color:#555;">No sentiment data</div>'}</div>
    <div class="stat-card"><h4>Daily Trend</h4>${trendSvg || '<div style="font-size:11px;color:#555;">Insufficient data</div>'}</div>
    <div class="stat-card"><h4>Top 5 Accessed</h4>${topList || '<div style="font-size:11px;color:#555;">No data</div>'}</div>
  `;
}
</script>
</body>
</html>"""


# ═══════════════════════════════════════
#  Timeline View HTML
# ═══════════════════════════════════════

TIMELINE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cortex Memory Timeline</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Inter', sans-serif;
    background: #08080f;
    color: #d0d0e0;
    min-height: 100vh;
    padding: 0;
  }

  #tl-header {
    position: sticky; top:0; z-index:10;
    display: flex; align-items: center; justify-content: space-between;
    padding: 18px 32px;
    background: rgba(8,8,15,0.95); backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(96,165,250,0.1);
  }
  #tl-header h1 {
    font-size: 16px; font-weight: 700; letter-spacing: 3px;
    background: linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .back-btn {
    padding: 6px 16px; border-radius: 20px; font-size: 11px;
    font-family: 'Inter', sans-serif; cursor: pointer;
    border: 1px solid rgba(96,165,250,0.2);
    background: rgba(96,165,250,0.08); color: #60a5fa;
    text-decoration: none; font-weight: 500;
    transition: all 0.2s;
  }
  .back-btn:hover { background: rgba(96,165,250,0.2); }

  #timeline {
    position: relative;
    padding: 40px 60px;
    max-width: 1200px;
    margin: 0 auto;
  }

  /* Center Axis */
  #timeline::before {
    content: '';
    position: absolute;
    left: 50%;
    top: 0; bottom: 0;
    width: 2px;
    background: linear-gradient(180deg, rgba(96,165,250,0.3), rgba(167,139,250,0.1));
    transform: translateX(-50%);
  }

  .tl-item {
    position: relative;
    width: 45%;
    padding: 20px 24px;
    background: rgba(16,16,28,0.8);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    margin-bottom: 24px;
    transition: border-color 0.3s, transform 0.2s;
    cursor: default;
  }
  .tl-item:hover {
    border-color: rgba(96,165,250,0.3);
    transform: translateY(-2px);
  }
  .tl-item.left { margin-right: auto; margin-left: 0; }
  .tl-item.right { margin-left: auto; margin-right: 0; }

  /* Connection Point */
  .tl-item::after {
    content: '';
    position: absolute;
    top: 28px;
    width: 12px; height: 12px;
    border-radius: 50%;
    background: #60a5fa;
    border: 2px solid #08080f;
  }
  .tl-item.left::after { right: -7%; transform: translateX(50%); }
  .tl-item.right::after { left: -7%; transform: translateX(-50%); }

  .tl-time {
    font-size: 10px; color: #a78bfa; letter-spacing: 1px;
    margin-bottom: 8px; font-weight: 500;
  }
  .tl-tag {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 10px; font-weight: 600; margin-bottom: 8px;
    background: rgba(96,165,250,0.15); color: #60a5fa;
  }
  .tl-sentiment {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 10px; margin-left: 6px;
  }
  .tl-summary { font-size: 13px; line-height: 1.6; color: #bbb; }
  .tl-importance {
    margin-top: 10px; font-size: 10px; color: #555;
  }
  .tl-importance span { color: #fbbf24; font-weight: 600; }

  .tl-empty {
    text-align: center; padding: 80px; color: #444; font-size: 14px;
  }

  /* Sentiment Colors */
  .sent-positive { background: rgba(52,211,153,0.15); color: #34d399; }
  .sent-negative { background: rgba(239,68,68,0.15); color: #ef4444; }
  .sent-neutral { background: rgba(107,114,128,0.15); color: #6b7280; }
  .sent-mixed { background: rgba(251,191,36,0.15); color: #fbbf24; }

  /* Animation */
  .tl-item { opacity: 0; animation: fadeSlideIn 0.5s forwards; }
  @keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
</head>
<body>
<div id="tl-header">
  <h1>CORTEX TIMELINE</h1>
  <a href="/" class="back-btn">← Back to 3D View</a>
</div>

<div id="timeline">
  <div class="tl-empty" id="tl-loading">Loading memories...</div>
</div>

<script>
async function loadTimeline() {
  const res = await fetch('/api/graph_data');
  const data = await res.json();
  const tl = document.getElementById('timeline');

  // Sort by time (latest first)
  const nodes = data.nodes.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  if (nodes.length === 0) {
    tl.innerHTML = '<div class="tl-empty">No memory records found</div>';
    return;
  }

  tl.innerHTML = '';
  nodes.forEach((n, i) => {
    const side = i % 2 === 0 ? 'left' : 'right';
    const sentClass = n.sentiment ? 'sent-' + n.sentiment : 'sent-neutral';
    const sentLabel = n.sentiment || 'neutral';
    const time = new Date(n.created_at).toLocaleString('en-US', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });

    const card = document.createElement('div');
    card.className = 'tl-item ' + side;
    card.style.animationDelay = (i * 0.05) + 's';
    card.innerHTML = `
      <div class="tl-time">${time}</div>
      <span class="tl-tag">${n.summary_l0 || '—'}</span>
      <span class="tl-sentiment ${sentClass}">${sentLabel}</span>
      <div class="tl-summary">${n.summary_l1 || n.label || n.content.substring(0, 80) + '...'}</div>
      <div class="tl-importance">Importance <span>${n.importance}</span> · Access <span>${n.access_count}</span>x · ${n.persona || 'default'}</div>
    `;
    tl.appendChild(card);
  });
}
loadTimeline();
</script>
</body>
</html>"""

# ═══════════════════════════════════════
#  Coding Sync HTML
# ═══════════════════════════════════════
CODING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cortex Coding Mode</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  * { box-sizing: border-box; }
  body { font-family: 'Inter', sans-serif; background: #08080f; color: #e2e8f0; margin: 0; padding: 0; min-height: 100vh; }
  #header { background: rgba(16,16,28,0.95); padding: 16px 32px; border-bottom: 1px solid rgba(96,165,250,0.2); display: flex; justify-content: space-between; align-items: center; }
  h1 { margin: 0; font-size: 16px; color: #60a5fa; letter-spacing: 2px; }
  .btn { background: rgba(96,165,250,0.1); border: 1px solid rgba(96,165,250,0.3); color: #60a5fa; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 11px; transition: 0.3s; }
  .btn:hover { background: rgba(96,165,250,0.2); }
  .container { display: flex; gap: 24px; padding: 24px 32px; height: calc(100vh - 65px); }
  .col { flex: 1; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
  .col-header { padding: 16px; background: rgba(0,0,0,0.2); border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 600; font-size: 13px; color: #f472b6; display: flex; align-items: center; }
  .col-header span { font-size: 10px; color: #888; font-weight: 400; margin-left: auto; }
  .col-input { padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; flex-direction: column; gap: 10px; }
  textarea { width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); color: #fff; padding: 12px; border-radius: 6px; font-family: monospace; resize: vertical; min-height: 80px; }
  textarea:focus { border-color: #60a5fa; outline: none; }
  .list { flex: 1; overflow-y: auto; padding: 16px; }
  .card { background: rgba(16,16,28,0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 16px; margin-bottom: 12px; transition: transform 0.2s;}
  .card:hover { border-color: rgba(96,165,250,0.3); transform: translateY(-2px); }
  .req-card { border-left: 4px solid #f472b6; }
  .cmt-card { border-left: 4px solid #34d399; }
  .meta { display: flex; justify-content: space-between; font-size: 10px; color: #888; margin-bottom: 10px; }
  .val { color: #fbbf24; }
  .content { font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; color: #d1d5db; }
  .del-btn { color: #ef4444; cursor: pointer; float:right; background: none; border: none; font-size:12px; opacity:0; transition: 0.2s; }
  .card:hover .del-btn { opacity: 0.7; }
  .del-btn:hover { opacity: 1; transform: scale(1.1); }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
</style>
</head>
<body>
  <div id="header">
    <h1><span style="color:#fff">CORTEX</span> CODING SYNC</h1>
    <button class="btn" onclick="location.href='/'">🔙 Back to Brain View</button>
  </div>
  <div class="container">
    <div class="col">
      <div class="col-header" style="color: #f472b6">📋 Product Requirements <span>Core Spec</span></div>
      <div class="col-input">
        <textarea id="req-input" placeholder="Enter feature requirements or specs here..."></textarea>
        <button class="btn" style="align-self: flex-end; background: rgba(244,114,182,0.1); border-color: #f472b6; color: #f472b6" onclick="addMem('req')">📝 Save Requirement</button>
      </div>
      <div class="list" id="req-list"></div>
    </div>
    <div class="col">
      <div class="col-header" style="color: #34d399">🚀 Code Commits <span>Development Progress</span></div>
      <div class="col-input">
        <textarea id="cmt-input" placeholder="Add code snippets or change logs..."></textarea>
        <button class="btn" style="align-self: flex-end; background: rgba(52,211,153,0.1); border-color: #34d399; color: #34d399" onclick="addMem('cmt')">💾 Save Commit</button>
      </div>
      <div class="list" id="cmt-list"></div>
    </div>
  </div>

<script>
async function load() {
  const r = await fetch('/api/graph_data');
  const d = await r.json();
  const reqs = d.nodes.filter(n => (n.concept_tags || []).includes('coding_requirement')).sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
  const cmts = d.nodes.filter(n => (n.concept_tags || []).includes('code_commit')).sort((a,b) => new Date(b.created_at) - new Date(a.created_at));

  document.getElementById('req-list').innerHTML = reqs.map(n => 
    `<div class="card req-card">
      <button class="del-btn" title="Delete" onclick="del('${n.id}')">✕</button>
      <div class="meta"><span>🏷️ ${n.summary_l0 || 'Requirement'} | ID: ${n.id.substring(0,8)}</span><span>Imp: <span class="val">${Number(n.importance).toFixed(1)}</span></span></div>
      <div class="content">${n.content}</div>
    </div>`
  ).join('');

  document.getElementById('cmt-list').innerHTML = cmts.map(n => 
    `<div class="card cmt-card">
      <button class="del-btn" title="Delete" onclick="del('${n.id}')">✕</button>
      <div class="meta"><span>📂 ${n.summary_l0 || 'Commit'} | ID: ${n.id.substring(0,8)}</span><span>🕒 ${new Date(n.created_at).toLocaleString('en-US')}</span></div>
      <div class="content" style="font-family: monospace; font-size:12px;">${n.content}</div>
    </div>`
  ).join('');
}

async function addMem(type) {
  const isReq = type === 'req';
  const input = document.getElementById(isReq ? 'req-input' : 'cmt-input');
  if(!input.value.trim()) return;

  const btn = event.target;
  const oldText = btn.innerText;
  btn.innerText = 'Processing...';
  btn.disabled = true;

  const body = {
    content: input.value.trim(),
    importance: isReq ? 1.0 : 0.6,
    concept_tags: [isReq ? 'coding_requirement' : 'code_commit'],
    memory_kind: isReq ? 'semantic' : 'episodic',
    persona: 'default'
  };

  try {
    const res = await fetch('/api/memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (res.ok) {
      alert('Saved successfully!');
      input.value = '';
      load();
    } else {
      alert('Save failed');
    }
  } finally {
    btn.innerText = oldText;
    btn.disabled = false;
  }
}

async function del(id) {
  if(!confirm('Are you sure you want to delete this memory?')) return;
  const res = await fetch(`/api/memory/${id}`, { method: 'DELETE' });
  if(res.ok) load();
}

load();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print("Cortex Memory Dashboard")
    print("http://localhost:8000")
    print("http://localhost:8000/timeline")
    print("Ctrl+C to stop\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
