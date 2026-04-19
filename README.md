# 🧠 Cortex Memory Engine 2.0
> **Non-Linear Hierarchical Memory Engine: A Persistent Digital Brain for Sophisticated AI Agents**

[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/Vector-pgvector-FF6F61?style=for-the-badge)](https://github.com/pgvector/pgvector)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)

---

## 🌌 Design Philosophy

In traditional Agent systems, context window limitations often lead to "memory explosion" or the loss of critical background information.
**Cortex Memory Engine** is designed to mimic human cognitive processes through "Dynamic Salience Ranking," "Autonomous Abstraction," and "Tiered Archiving." It provides AI agents with true long-term memory and deep reasoning capabilities without the overhead of massive raw logs.

---

## 🧬 Cognitive Architecture

Cortex implements a **4-Layer Vertical Memory Model** to balance breadth and depth of recall:

### 1. Raw Input Layer (Verbatim / L2) - **"Sensory Buffer"**
- **Purpose**: Immutable logs of 100% raw conversations or code.
- **Intent**: Preventing information loss during summarization (e.g., retaining exact variable names or user tone).

### 2. Episodic Memory Layer (Events / L1) - **"The Stream"**
- **Purpose**: Condensed, chronological event summaries ("What happened today?").
- **Intent**: Providing temporal retrieval capabilities and timeline-based reasoning.

### 3. Fact Memory Layer (Semantic) - **"Knowledge Extraction"**
- **Purpose**: Structured facts extracted from episodes (e.g., "User prefers React", "Project deadline is May 1st").
- **Intent**: Breaking temporal boundaries to form permanent, cross-session knowledge.

### 4. Concept Memory Layer (Abstraction) - **"Neural Clusters"**
- **Purpose**: Automatically associating multiple facts into high-level conceptual maps.
- **Intent**: Enabling non-literal semantic association, analogous to human imagination and intuition.

---

## 🚀 System Showcase

### 1. 3D Neural Knowledge Graph
![3D Neural Graph](assets/demo_3d_graph.png)
*Demonstrating **Autonomous Semantic Clustering**. The system uses the `BGE-M3` model and `pgvector` to group 90+ memories into distinct thematic clusters based on cosine similarity.*

### 2. Cognitive Episodic Timeline
![Cognitive Timeline](assets/demo_timeline.png)
*Visualizing the **Episodic Memory Stream**. This view tracks interactions in chronological order, allowing the agent to perform "Mental Time Travel" for precise context retrieval.*

### 3. Developer Coding Sync
![Coding Sync](assets/demo_coding_sync.png)
*Demonstrating **Context-Aware Development**. A specialized interface for managing high-priority requirements and code snapshots, balancing deep history with core specifications (L0/L1).*

---

## 🔮 Neural Ranking Engine

The "Soul" of Cortex is its decision engine for what to "remember." We implement a dynamic scoring algorithm with **12 weigh-dimensions**:

| Metric | Weight | Design Rationale |
| :--- | :--- | :--- |
| **Similarity** | 20% | Core vector space alignment with the current query. |
| **Recency** | 12% | Implementation of the Ebbinghaus Forgetting Curve. |
| **Importance** | 14% | Manual or AI-assigned significance (salience). |
| **Frequency** | 8% | "Active" info that is mentioned often stays in prime context. |
| **Reinforcement** | 10% | Manual/Automatic "strengthening" based on successful outcomes. |
| **Token Efficiency** | 10% | Prioritizing concise, summarized nodes to save costs. |
| **Emotion/Sentiment** | 6% | Prioritizing emotionally relevant context for better alignment. |
| **Novelty** | 4% | Penalty for redundant information to ensure diverse retrieval. |

---

## 💤 Memory Lifecycle (Sleep Cycle)

Cortex performs autonomous background maintenance during "Sleep":
1. **Intelligent Deduplication**: When similarity > 0.96, redundant memories are merged to keep the "mind" lean.
2. **Neural Decay**: Trivial or low-frequency information fades over time to keep working memory clean of noise.
3. **Consolidation**: Frequently recurring episodic patterns are consolidated into permanent semantic facts.

---

## 🛠️ Tech Stack

- **Linguistic Engine**: Python 3.10+
- **Database**: PostgreSQL + pgvector (High-performance vector retrieval)
- **Embeddings**: Ollama: `bge-m3` (Multilingual, high-dimensional representation)
- **Framework**: FastAPI (Asynchronous high-performance APIs)
- **Visualization**: Three.js / Force-Graph (Hardware-accelerated 3D rendering)

---

## 📬 Roadmap
- [ ] **Collaborative Mind**: Secure cross-agent brain communication.
- [ ] **Multimodal Synthesis**: Storing and retrieving semantic features from images and audio.
- [ ] **Proactive Recall**: Automatic agent "alerts" based on background contextual relevance.

---
*Developed with Passion for the Evolution of AI Cognition.*
