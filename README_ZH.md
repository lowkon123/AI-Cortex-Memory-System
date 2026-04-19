# 🧠 Cortex Memory Engine 2.0
> **非線性分層記憶引擎：為強 AI Agent 打造的「長效數位大腦」**

[中文版 (Chinese)](README_ZH.md) | [English](README.md)

[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/Vector-pgvector-FF6F61?style=for-the-badge)](https://github.com/pgvector/pgvector)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)

---

## 🌌 設計初衷 (Design Philosophy)

在傳統的 Agent 系統中，上下文 (Context) 往往隨著對話增長而「爆炸」，導致記憶遺忘或 LLM 處理成本飆升。
**Cortex Memory Engine** 的誕生，是為了模擬人類大腦的認知機制，透過「動態重要性」、「自動抽象化」與「分層歸檔」技術，讓 AI 具備真正的長期、具備深度推理背景的記憶能力。

---

## 🧬 認知結構 (Cognitive Architecture)

Cortex 採用 **四層垂直記憶模型**，確保系統在廣度與深度之間取得完美平衡：

### 1. 原始輸入層 (Raw Input / L2) - **「瞬時感官」**
- **用途**：記錄 100% 原始對話或代碼。
- **設計用意**：防止在後續摘要過程中遺失關鍵細節（如具體的變數名稱或用戶語氣）。

### 2. 事件記憶層 (Episodic Memory / L1) - **「經歷流」**
- **用途**：將 Raw 數據處理為按時間排序的「事件摘要」。
- **設計用意**：讓系統知道「發生了什麼」，提供時間維度的檢索能力。

### 3. 事實知識層 (Fact Memory / Semantic) - **「知識提取」**
- **用途**：從事件中萃取出結構化的事實（例：用戶偏好 React、工作時間是深夜）。
- **設計用意**：打破時間限制，形成跨時間點的永久知識。

### 4. 抽象概念層 (Concept Memory) - **「認知群集」**
- **用途**：自動將多個事實關聯為更高層級的概念圖譜。
- **設計用意**：實現非感官的語意聯想，類比人類的「聯想力」。

---

## 🚀 系統實機演示

### 1. 3D 神經知識圖譜
![3D Neural Graph](assets/demo_3d_graph.png)
*展示 **自動語意群集 (Autonomous Semantic Clustering)**。系統利用 `BGE-M3` 向量模型與 `pgvector` 技術，自動將 90+ 筆記憶歸類為不同的主題簇，並根據餘弦相似度建立神經連結。*

### 2. 認知事件時間軸
![Cognitive Timeline](assets/demo_timeline.png)
*展示 **事件記憶流 (Episodic Memory Stream)**。此視圖依時間順序追蹤每一次交互與思考，使 AI 代理能夠進行「心理時間旅行」，精準檢索過去的上下文背景。*

### 3. 開發編碼同步介面
![Coding Sync](assets/demo_coding_sync.png)
*展示 **上下文感知開發 (Context-Aware Development)**。專為管理高優先級產品需求與代碼快照而設計，展現系統在維護核心規格 (L0/L1) 的同時，如何保留深度的開發迭代歷史。*

---

## 🔮 神經排名引擎 (Neural Ranking Engine)

Cortex 的「靈魂」在於它如何決定哪些記憶該被「記起」。我們實作了一個擁有 **12 個權重維度** 的動態評分算法：

| 指標 | 權重 | 設計用意 |
| :--- | :--- | :--- |
| **語意相似度 (Similarity)** | 20% | 確保記憶與當前問題的關聯性。 |
| **新鮮度 (Recency)** | 12% | 模擬艾賓浩斯遺忘曲線，優先調用最近的資訊。 |
| **核心重要性 (Importance)** | 14% | 區分「瑣事」與「核心需求」。 |
| **使用頻率 (Frequency)** | 8% | 越常被提起的資訊，在大腦中越「活躍」。 |
| **強化反饋 (Reinforcement)** | 10% | 根據用戶的滿意度手動或自動「加固」記憶。 |
| **Token 效率 (Efficiency)** | 10% | 優先選擇資訊密度高（摘要過）的節點，節省成本。 |
| **情感權重 (Emotion)** | 6% | 重視帶有強烈情感色彩的紀錄，捕捉用戶情緒。 |
| **新鮮感 (Novelty)** | 4% | 分散檢索結果，防止系統陷入冗餘的循環中。 |

---

## 💤 記憶生命週期 (Sleep Cycle)

系統具備自主維護能力，在背景運行的「睡眠週期」會定時處理：
1. **智能去重 (Deduplication)**：當相似度 > 0.96 時，自動合併冗餘記憶，保持大腦精簡。
2. **神經衰減 (Neural Decay)**：不重要且低頻率的訊息隨時間消逝，確保「工作記憶」欄位不被雜訊佔用。
3. **固化 (Consolidation)**：將頻繁發生的事件 (Episodes) 固化為永久事實 (Facts)。

---

## 🛠️ 技術棧 (Tech Stack)

- **核心語言**: Python 3.10+
- **向量數據庫**: PostgreSQL + pgvector (高效相似度檢索)
- **嵌入模型**: Ollama: `bge-m3` (支持多語言、多維度語意表示)
- **Web 框架**: FastAPI (異步高性能接口)
- **前端可視化**: Three.js / Force-Graph (硬體加速 3D 渲染)

---

## 📬 未來展望 (Roadmap)
- [ ] **Agent-to-Brain 同步機制**：讓新開發代理不需要「重讀全專案代碼/文檔」，只需從 Cortex 記憶獲取事實即可立即上手。
- [ ] **協作記憶機制**：支持多個 Agent 之間的安全大腦通訊。
- [ ] **多模態記憶**：存儲與檢索圖片、音檔的語意特徵。

---
*Developed with Passion for the Evolution of AI Cognition.*
