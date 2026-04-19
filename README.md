# Cortex Memory Engine

[繁體中文版](./README_ZH.md)

> **"It's not just document storage; it's memory for thinking systems."**

Cortex Memory Engine is a local, long-term memory layer designed for AI agents. It goes beyond simple vector search by modeling memory like a living organism—formed, compressed, recalled, reinforced, and forgotten.

---

## 🧠 Core Philosophy: Why Cortex?

Traditional RAG and vector databases treat memory as static data. Cortex treats memory as a **dynamic cognitive process**:

### 1. Hierarchical Architecture (L0 / L1 / L2)
- **L0 (Sensory)**: Immediate conversation context.
- **L1 (Short-term)**: Recent technical decisions and temporary requirements.
- **L2 (Long-term)**: Consolidated architectural patterns and core user preferences.

### 2. Dynamic Activation & Recall
In Cortex, **Similarity != Usefulness**. We use a multi-factor **Activation Score**:
`Recall Score = Semantic Similarity + Importance Weight + Access Frequency + Emotional Weight - Time Decay`
This ensures your AI recalls what actually matters, not just what sounds similar.

### 3. Native Forgetting & Consolidation
- **Forgetting Mechanism**: Obsolete or weak memories naturally fade away to prevent "Context Explosion" and keep your AI focused.
- **Sleep Cycle (Consolidation)**: During idle time, the system automatically runs a background cycle to summarize fragmented logs into high-density semantic nodes.

### 4. Extreme Token Efficiency
Cortex follows a "Summary First, Details on Demand" strategy. Agents retrieve high-value summaries by default, only expanding into raw data when a deep dive is required. This maximizes utility while minimizing LLM costs.

---

## 🚀 Quick Start (Zero to Hero)

Set up your production-ready memory system in minutes, even on a fresh machine:

### 1. Prerequisites
- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (For the DB)
- [Ollama](https://ollama.com/download) (For local embeddings)

### 2. Environment Setup
```bash
# 1. Clone & Enter
git clone https://github.com/lowkon123/AI-Cortex-Memory-System.git
cd AI-Cortex-Memory-System

# 2. Virtual Env
python -m venv venv
# Windows:
.\venv\Scripts\activate

# 3. Install & Model
pip install -r requirements.txt
ollama pull bge-m3
```

### 3. Launch
1.  **DB**: `docker compose up -d`
2.  **All-in-One** (Windows): Double-click `launch_services.bat`.
3.  **Manual**: Open `http://localhost:8000` for the dashboard.

---

## 🏗 Key Components

### 📊 3D Memory Dashboard
- File: [dashboard.py](dashboard.py)
- **3D Memory Graph**: Visualize clusters and relationships between memory nodes in real-time.
- **Interactive Inspection**: Double-click any node to see its activation score and history.

### 💬 Cognitive Chat Demo
- File: [chat.py](chat.py)
- A live showcase of AI performing "Recall before Generation" and "Reinforcement after Action."

### 🔌 Universal API & MCP Server
- Folder: [api](api) / [cortex_mcp_server.py](cortex_mcp_server.py)
- Seamlessly plug Cortex into Claude Code, Cursor, or your custom agents.

---

## 🔧 Integration Pattern
Simple REST loop for any AI agent:
1. `POST /agent/context` (Get dynamic background)
2. Append background to LLM prompt.
3. `POST /agent/store` (Commit decision/result)

Detailed Guidelines: [CORTEX_AI_INSTRUCTIONS.md](./CORTEX_AI_INSTRUCTIONS.md)
