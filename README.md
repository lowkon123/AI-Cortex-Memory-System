# 🧠 Cortex Memory Engine 2.0
> **Non-Linear Hierarchical Memory Engine: A Persistent Digital Brain for Sophisticated AI Agents**

[中文版 (Chinese)](README_ZH.md) | [English](README.md)

---

## 🌌 Design Philosophy

In traditional Agent systems, context window limitations often lead to "memory explosion" or the loss of critical background information.
**Cortex Memory Engine** is designed to mimic human cognitive processes through "Dynamic Salience Ranking," "Autonomous Abstraction," and "Tiered Archiving." It provides AI agents with true long-term memory and deep reasoning capabilities without the overhead of massive raw logs.

---

## 🧬 Core Architecture

### 1. 4-Layer Vertical Memory Model
Cortex implements a **4-layer vertical memory model** to balance breadth and depth of recall:
- **Raw Input Layer (Verbatim / L2)**: Immutable logs of 100% raw conversations. Prevents loss of critical details (e.g., variable names).
- **Episodic Memory Layer (Events / L1)**: Summarizes data into chronological "Event Streams" for temporal reasoning.
- **Fact Memory Layer (Semantic)**: Extracts permanent, cross-session knowledge (e.g., "User prefers React").
- **Concept Memory Layer (Abstraction)**: Associating multiple facts into high-level conceptual maps for non-linear intuition.

### 2. Memory Zooming Logic (L0-L2)
Supports dynamic granularity of context injection:
- **L0 (Summary)**: Core intent only. Best for extremely long-span background injection.
- **L1 (Key Points)**: Bulleted takeaways. Best for specific task execution.
- **L2 (Raw Content)**: Verbatim data. Best for code generation or exact reproduction.

---

## 🔍 Hybrid Search & Navigation

### 1. Hybrid RAG Architecture
Cortex combines two powerful search paradigms:
- **Full-Text Search (FTS)**: Utilizing PostgreSQL `tsvector` for exact keyword matching (UUIDs, specific function names).
- **Vector Cosine Similarity**: Utilizing `pgvector` and `BGE-M3` for deep semantic association.
- **Weighted Fusion**: Automatically balances keyword precision with semantic ambiguity.

### 2. Proactive Context Scanning
The system runs "Scanning Probes" in the background to simulate human contemplation:
- **Relevance Discovery**: Actively finding deep links between the current task and historical logs from months ago.
- **Pre-emptive Injection**: Pre-loading "highly probable context" into the cache before the agent even asks.

---

## 🔮 Neural Ranking & Activation

The "Soul" of Cortex is governed by a **12-Dimension Scoring Algorithm**:

| Metric | Weight | Design Rationale |
| :--- | :--- | :--- |
| **Similarity** | 20% | Vector space alignment with the current query. |
| **Recency** | 12% | **Ebbinghaus Decay**: Natural score drop-off over time. |
| **Importance** | 14% | Priority for core requirements over trivial logs. |
| **Frequency** | 8% | Reflects how "Active" a memory is in the brain. |
| **Reinforcement** | 10% | Increases "Neural Strength" based on task successes. |
| **Token Efficiency** | 10% | Prioritizing high-density summaries to save LLM costs. |
| **Emotion/Sentiment** | 6% | Prioritizing emotionally salient context. |
| **Novelty** | 4% | Penalty for redundant info to ensure diverse retrieval. |

---

## 💤 Memory Lifecycle Management

### 1. The Sleep Cycle
Mimicking human neuroplasticity during rest:
- **Intelligent Deduplication**: When similarity > 0.96, redundant memories are merged, accumulating importance weights.
- **Conflict Resolution**: When new facts contradict old ones, a `SUPERSEDES` link is created, flagging outdated logs.

### 2. Reinforcement Learning Loop
Built-in `Success Count` mechanism. When a memory is successfully used to solve a problem, its "Neural Path" is thickened, giving it higher retrieval priority in the future.

---

## 🛡️ Privacy, Security & Performance

### 1. Privacy-First Local Deployment
- **Ollama Integration**: All embeddings and extractions run locally (e.g., `bge-m3` or `llama3`), ensuring zero data leakage to the cloud.
- **Multi-Persona Isolation**: Securely segregating memory namespaces for different Agents or Users within the same DB.

### 2. High-Performance Indexing (pgvector)
- Mature PostgreSQL ecosystem supporting `HNSW` (Hierarchical Navigable Small Worlds) indexing.
- Sub-millisecond vector retrieval across millions of memory nodes.

---

## 🔌 Standardized Connectivity

### 1. MCP Protocol Support
Full support for the **Model Context Protocol (MCP)**. Cortex can seamlessly connect to:
- **Claude Desktop** / **VS Code (Cursor/Windsurf)**
- Any AI framework supporting the MCP standard.

### 2. Agent-to-Brain Sync Philosophy
The core mission: New agents shouldn't spend hours "reading" your docs. They connect to the Cortex and immediately inherit "Digested Project Facts."

---

## 🚀 System Showcase

### 1. 3D Neural Knowledge Graph
![3D Neural Graph](assets/demo_3d_graph.png)
*Demonstrating **Autonomous Semantic Clustering**. Visualizing how memory naturally groups into thematic hubs.*

### 2. Cognitive Episodic Timeline
![Cognitive Timeline](assets/demo_timeline.png)
*Visualizing the **Episodic Memory Stream**. Enabling precise "Mental Time Travel".*

### 3. Developer Coding Sync
![Coding Sync](assets/demo_coding_sync.png)
*Demonstrating **Context-Aware Development**. Deep management of code snapshots and L0/L1 requirements.*

---

## 📬 Roadmap
- [x] **Agent-to-Brain Sync**: Out-of-the-box expert context inheritance.
- [ ] **Multimodal Synthesis**: Storing and retrieving features from images and audio.
- [ ] **Collective Mind**: Secure sharing of non-private facts across multiple brains.

---
*Developed with Passion for the Evolution of AI Cognition.*
