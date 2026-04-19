# Cortex Memory Engine 🧠 [Awesome!!!]

[繁體中文版](./README_ZH.md)

> **"Not just document storage, but memory for thinking systems. Modeled after human cognition with native forgetting and consolidation."**

Cortex is a **dynamic cognitive memory layer** designed for AI agents. It eliminates the limitations of static RAG and context-window bloat by treating memory as a living process.

---

## ⚡ Why Cortex? (Vs. Traditional Vector DBs)

| Feature | Trad. Vector DB / RAG | Cortex Memory Engine |
| :--- | :--- | :--- |
| **Retrieval Logic** | Purely Semantic Similarity (Cosine) | **Multi-factor Activation Score** (Similarity + Recency + Heat + Importance) |
| **Data State** | Static & Permanent | **Dynamic Flow** (Forgets, Compresses, and Reinforces) |
| **Context Cost** | Linear growth, prone to bloat | **Ultra-Efficient** (Auto-summarization, detailed on-demand) |
| **Background Ops** | None | **Sleep Cycle** (Background consolidation and garbage collection) |
| **Evolution** | Passive | **Proactive Scoring** (Self-improves based on agent feedback) |

---

## 🏗 Core Architecture: The Memory Lifecycle

In Cortex, every memory is a node with its own "metabolism":

### 1. The Memory Hierarchy (Tier)
- **L0 - Sensory**: Immediate session-specific context.
- **L1 - Episodic**: Recent technical decisions and temporary project requirements.
- **L2 - Semantic**: Consolidated knowledge nodes and core user preferences.

### 2. The Data Model: Inside a Memory Node [Awesome!!!]
| Property | Description | Impact |
| :--- | :--- | :--- |
| **Importance** | Core value (0-1) | Determines if a memory is locked or eligible for forgetting. |
| **Confidence** | Reliability score | Influences the weight of the memory in AI decision-making. |
| **Emotional Weight** | Intensity score | Automatically adjusted to simulate "Flashbulb Memories." |
| **Access Count** | Usage frequency | Increases every time the memory is successfully recalled. |
| **Activation Score** | **Current Vitality** | Determines if the memory "surfaces" to the AI at this moment. |

---

## 🚀 Quick Start (Zero to Hero)

Launch your production-ready memory system in minutes:

### 1. Prerequisites
- [Python 3.10+](https://www.python.org/downloads/) / [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) / [Ollama](https://ollama.com/download)

### 2. Environment Setup
```bash
git clone https://github.com/lowkon123/AI-Cortex-Memory-System.git
cd AI-Cortex-Memory-System
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
ollama pull bge-m3
```

### 3. Launch
1. **DB**: `docker compose up -d`
2. **Auto-Launch** (Windows): Double-click `launch_services.bat`.
   - **3D Dashboard**: `http://localhost:8000`
   - **Memory API**: `http://localhost:8002`

---

## 🔌 API Reference: Developer Core

| Type | Endpoint | Description |
| :--- | :--- | :--- |
| **Agent Link** | `POST /agent/context` | **Most Used!** Get formatted prompt context directly. |
| **Store** | `POST /agent/store` | Persist technical decisions, requirements, or results. |
| **Refine** | `POST /agent/reinforce` | Strengthen a memory node based on its utility. |
| **Analytics** | `GET /search/stats` | View health and distribution stats of the memory pool. |

### Python Integration:
```python
from api.client import MemoryClient
client = MemoryClient("http://localhost:8002", persona="antigravity")

# 1. Build context for a prompt
context = client.build_context("How to optimize DB?", limit=5)

# 2. Store a new architectural decision
client.agent_store(content="We decided to use pgvector for indexing.", tags=["db", "opt"])
```

---

## 📊 Visualization & Interaction
*   **3D Graph Dashboard (dashboard.py)**: Real-time visualization of memory clusters and semantic relationships.
*   **Cognitive Chat Demo (chat.py)**: A standalone playground to test recall and reinforcement logic.

---

## 🔧 AI Agent Standard
We have designed specific guidelines for AI Agents using this system.
👉 [**CORTEX_AI_INSTRUCTIONS.md (Mandatory)**](./CORTEX_AI_INSTRUCTIONS.md)

---
*Cortex Memory Engine - Not just storage. Giving AI a soul.*
