# 🧠 Cortex Memory Engine 2.0
> **非線性分層記憶引擎：為強 AI Agent 打造的「長效數位大腦」**

[中文版 (Chinese)](README_ZH.md) | [English](README.md)

---

## 🌌 設計初衷 (Design Philosophy)

在傳統的 Agent 系統中，上下文 (Context) 往往隨著對話增長而「爆炸」，導致記憶遺忘或 LLM 處理成本飆升。
**Cortex Memory Engine** 的誕生，是為了模擬人類大腦的認知機制，透過「動態重要性」、「自動抽象化」與「分層歸檔」技術，讓 AI 具備真正的長期、具備深度推理背景的記憶能力。

---

## 🧬 核心架構 (Core Architecture)

### 1. 四層垂直記憶模型 (Tiered Memory)
Cortex 採用 **四層垂直記憶模型**，確保系統在廣度與深度之間取得完美平衡：
- **原始輸入層 (Raw Input / L2)**：記錄 100% 原始對話。防止摘要過程中遺失關鍵細節。
- **事件記憶層 (Episodic Memory / L1)**：將數據處理為按時間排序的「事件摘要」，提供時間維度的檢索。
- **事實知識層 (Fact Memory / Semantic)**：從事件中萃取出跨時間點的永久知識。
- **抽象概念層 (Concept Memory)**：自動將多個事實關聯為更高層級的概念圖譜。

### 2. 記憶縮放技術 (Memory Zooming: L0-L2)
系統支持動態調整內容精細度：
- **L0 (Summary)**: 僅提取核心意圖，適合極長跨度的背景注入。
- **L1 (Key Points)**: 提取條列式要點，適合具體任務執行。
- **L2 (Raw Content)**: 完整原始內容，適合需要精確複製或代碼生成的場景。

---

## 🔍 混合搜尋與導航 (Search Engine)

### 1. 混合搜尋 (Hybrid RAG)
Cortex 不僅僅依賴向量，它結合了兩種搜尋範式：
- **全文檢索 (Elastic-like FTS)**：利用 PostgreSQL 的 `tsvector` 進行精確關鍵字匹配（如搜索特定的 UUID 或變數名）。
- **向量餘弦相似度 (Vector Similarity)**：利用 `pgvector` 與 `BGE-M3` 模型進行語意關聯檢索。
- **加權融合 (Weighted Fusion)**：自動平衡關鍵字精確度與語意模糊度。

### 2. 主動式背景掃描 (Proactive Scanning)
系統在閒置時會自動運行「掃描探針」，模擬大腦的沉思過程：
- **關連性發現**：主動尋找當前任務與數月前歷史背景的深層聯想。
- **提示詞注入**：在 Agent 提問前，主動將「可能需要的背景」預加載至緩存中。

---

## 🔮 神經排名與激活 (Neural Ranking)

Cortex 決定「想起什麼」的邏輯由 **12 個權重指標** 組成：

| 指標 | 權重 | 設計用意 |
| :--- | :--- | :--- |
| **語意相似度 (Similarity)** | 20% | 向量空間的對齊程度。 |
| **新鮮度 (Recency)** | 12% | **艾賓浩斯衰減**：隨時間推移分數自然下降。 |
| **核心重要性 (Importance)** | 14% | 優先處理用戶明確標註或系統判定的關鍵資訊。 |
| **使用頻率 (Frequency)** | 8% | 反映該記憶在大腦中的活躍程度。 |
| **強化反饋 (Reinforcement)** | 10% | 根據任務的成功次數增加記憶的「神經強度」。 |
| **Token 效率 (Efficiency)** | 10% | 鼓勵 AI 檢索已被壓縮、更高密度的摘要。 |
| **情感權重 (Emotion)** | 6% | 重視用戶情緒反應強烈的關鍵節點。 |
| **新鮮感 (Novelty)** | 4% | 分散檢索結果，防止輸出的內容過於重複冗餘。 |

---

## 💤 記憶生命週期管理 (Life-cycle)

### 1. 睡眠週期與整理 (The Sleep Cycle)
模擬人類睡眠時的記憶固化過程：
- **智能去重 (Deduplication)**：當兩條記憶相似度 > 0.96 時，系統會自動合併它們，並累加重要性權重。
- **衝突解決 (Conflict Resolution)**：當新事實與舊記憶衝突時，系統會建立 `SUPERSEDES` 連結，標註舊記憶為過時。

### 2. 強化學習循環 (Reinforcement Learning)
系統內建了 `Success Count` 機制。當某一條記憶被成功用於解決問題並獲得正向反饋時，該記憶的「神經通路」會被加厚，使其在未來的檢索中具備更高的權限。

---

## 🛡️ 安全、隱私與性能 (Infrastructure)

### 1. 在地化私有部署 (Privacy-First)
- **Ollama 整合**：所有 Embedding 生成與事實萃取均可在本地運行（如使用 `bge-m3` 或 `llama3`），確保數據不流向雲端。
- **多重人格隔離 (Multi-Persona)**：支持在同一數據庫中隔離不同 Agent 或 User 的記憶命名空間。

### 2. 高性能索引 (pgvector Optimization)
- 基於 PostgreSQL 的成熟生態，支持 `HNSW` (Hierarchical Navigable Small Worlds) 索引。
- 無論是數千條還是數百萬條記憶，都能實現毫秒級的向量檢索。

---

## 🔌 標準化接入 (Connectivity)

### 1. MCP 協議支持
系統完整支援 **Model Context Protocol (MCP)**。這意味著您的 Cortex 大腦可以無縫接入：
- **Claude Desktop** / **VS Code (Cursor/Windsurf)**
- 任何支持 MCP 的自動化 Agent 框架。

### 2. Agent-to-Brain 同步哲學
這是我設計這個系統的最高綱領：讓新加入的 Agent 不需要花費數小時「朗讀」您的專案文件。它只需要連結到 Cortex，就能立即獲得「已經被消化過的專案事實」。

---

## 🚀 系統實機演示

### 1. 3D 神經知識圖譜
![3D Neural Graph](assets/demo_3d_graph.png)
*展示 **自動語意群集**。自動將記憶歸類為主題簇並建立連結。*

### 2. 認知事件時間軸
![Cognitive Timeline](assets/demo_timeline.png)
*展示 **事件記憶流**。實現精準的「心理時間旅行」。*

### 3. 開發編碼同步介面
![Coding Sync](assets/demo_coding_sync.png)
*展示 **上下文感知開發**。針對代碼快照與需求的深度優先管理。*

---

## 📬 未來展望 (Roadmap)
- [x] **Agent-to-Brain 同步機制**：實現開箱即用的專家認知繼承。
- [ ] **多模態記憶傳感**：支持圖片與音訊語意檢索。
- [ ] **集體意識 (Collective Mind)**：安全地共享不同大腦間的非私密事實。

---
*Developed with Passion for the Evolution of AI Cognition.*
