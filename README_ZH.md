# Cortex Memory Engine (皮質記憶引擎) 🧠 [屌!!!]

[English Version](./README.md)

> **"不再是文件儲存，而是 AI 的第二大腦。模擬人類記憶，具備遺忘與鞏固邏輯。"**

Cortex 是一個為 AI 代理人打造的**動態記憶運算層**。它解決了傳統 AI 只能依賴「靜態資料檢索」或「過長上下文」的痛點。

---

## ⚡ 為什麼選擇 Cortex？ (與傳統向量資料庫對比)

| 功能 | 傳統向量資料庫 (RAG) | Cortex Memory Engine |
| :--- | :--- | :--- |
| **檢索邏輯** | 單純的語意相似度 (Cosine) | **多維度啟動分數** (相似度+熱度+重要性) |
| **數據狀態** | 靜態、永久儲存 | **動態流動** (會遺忘、會壓縮、會強化) |
| **Context 成本** | 隨數據量線性增加，容易爆量 | **極度節省** (自動壓縮摘要，只提供必要的細節) |
| **背景處理** | 無 | **睡眠循環** (自動清理垃圾記憶、鞏固核心知識) |
| **主動性** | 被動等待查詢 | **主動更新評分**，根據 AI 反饋自我進化 |

---

## 🏗 核心架構：記憶的生命週期

Cortex 將每一條記憶視為一個具備「生命」的節點：

### 1. 記憶層級 (Tier)
- **L0 - Sensory (感官)**: 瞬時對話。
- **L1 - Episodic (情節)**: 近期任務開發決策、暫存需求。
- **L2 - Semantic (語意)**: 經過多次強化，轉化為核心知識。

### 2. 資料模型：每一條記憶都包含 [屌!!!]
| 參數 | 說明 | 影響 |
| :--- | :--- | :--- |
| **Importance** | 重要性 (0-1) | 決定記憶是否會被優先遺忘或鎖定 |
| **Confidence** | 信心水準 | 影響 AI 在決策時的參考權重 |
| **Emotional Weight** | 情緒權重 | 根據語境自動調整，模擬強烈記憶 |
| **Success Count** | 成功次數 | 每次被成功召回並解決任務後會增加 |
| **Activation Score** | **目前的啟動值** | 決定此時此刻這條記憶是否「浮現」出來 |

---

## 🚀 快速啟動 (Zero to Hero)

即使是剛重灌的電腦，按順序執行以下流程即可完整運行：

### 1. 準備基礎工具
- [Python 3.10+](https://www.python.org/downloads/) / [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) / [Ollama](https://ollama.com/download)

### 2. 環境架設
```bash
git clone https://github.com/lowkon123/AI-Cortex-Memory-System.git
cd AI-Cortex-Memory-System
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
ollama pull bge-m3
```

### 3. 一鍵啟動
1. 啟動資料庫：`docker compose up -d`
2. 啟動所有服務：執行 `launch_services.bat`
   - **3D Dashboard**: `http://localhost:8000`
   - **Memory API**: `http://localhost:8002`

---

## 🔌 API 核心端點：開發者必看

| 類型 | 端點 (Endpoint) | 功能說明 |
| :--- | :--- | :--- |
| **AI 串接** | `POST /agent/context` | **最常用！** 直接獲取格式化好的 Prompt 背景 |
| **記憶存檔** | `POST /agent/store` | 將開發決策或需求持久化 |
| **強化學習** | `POST /agent/reinforce` | 告訴系統「這條記憶很有用」，增加未來提取率 |
| **搜索與分析**| `GET /search/stats` | 獲取整個記憶庫的健康度與統計資訊 |

### Python 串接範例：
```python
from api.client import MemoryClient
client = MemoryClient("http://localhost:8002", persona="antigravity")

# 1. 獲取記憶背景
context = client.build_context("如何優化資料庫?", limit=5)

# 2. 存入新決策
client.agent_store(content="我們決定採用 pgvector 進行索引優化。", tags=["db", "opt"])
```

---

## 🎨 視覺化與互動
*   **3D 圖譜 (dashboard.py)**: 動態觀察記憶節點如何聚類，支援雙擊檢查細節。
*   **對話演示 (chat.py)**: 一個內建的聊天機器人，展示它如何從 Cortex 裡「想起」舊事。

---

## 🔧 AI 指令規範 (Agent Standard)
我們專為 AI Agent 設計了一套規則。請務必查看：
👉 [**CORTEX_AI_INSTRUCTIONS.md (必讀)**](./CORTEX_AI_INSTRUCTIONS.md)

---
*Cortex Memory Engine - 不只是儲存，是為了讓 AI 具備靈魂。*
