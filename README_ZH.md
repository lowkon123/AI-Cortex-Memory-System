# Cortex Memory Engine (皮質記憶引擎)

[English Version](./README.md)

> **"這不僅僅是文件儲存，這是為思考系統準備的記憶體。"**

Cortex 是一個專為 AI 打造的本地長效記憶運算層。它不只是將資料丟進資料庫，而是模仿人類大腦的記憶模型，讓 AI 具備真正的「經驗累積」能力。

---

## 🧠 核心理念：為什麼它與眾不同？

傳統的 RAG (檢索增強生成) 或向量資料庫只是「靜態檢索」。Cortex 則將記憶視為**動態生命體**：

### 1. 層級化記憶 (Hierarchical Memory: L0 / L1 / L2)
- **L0 (感官記憶)**：即時對話上下文。
- **L1 (短期/情境記憶)**：近期發生的開發決策、暫時性的需求。
- **L2 (長期/語意記憶)**：經過鞏固的核心架構知識、使用者偏好。

### 2. 動態召回 (Dynamic Activation)
在 Cortex 中，**相似度 (Similarity) 並不等於重要性**。我們引入了「啟動評分」機制：
`Recall Score = 語意相似度 + 重要性權重 + 存取次數 (熱度) + 情緒權重 - 時間衰減`
這確保了 AI 找回的是「真正有用」的記憶，而不只是「字面上相似」的廢話。

### 3. 本能的遺忘與鞏固 (Forgetting & Consolidation)
- **遺忘機制**：過時、低重要性且長期未被存取的記憶會隨時間消失，防止 Context 爆炸。
- **睡眠循環 (Sleep Cycle)**：系統在閒置時會自動進行記憶鞏固，將破碎的紀錄壓縮成精簡的語意摘要。

### 4. 高度 Token 效率
採用「先摘要，後細節」的策略。AI 預設讀取高價值的記憶摘要，只有在需要深入研究時才展開原始資料，極大化節省您的 API 帳單。

---

## 🚀 快速啟動 (Zero to Hero)

即使是剛重灌的電腦，按順序執行以下流程即可完整運行：

### 1. 準備基礎工具
請確保您的電腦已安裝以下軟體：
- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (用於執行資料庫)
- [Ollama](https://ollama.com/download) (用於本地 AI 向量模型)

### 2. 環境設定
```bash
# 1. 複製專案與進入目錄
git clone https://github.com/lowkon123/AI-Cortex-Memory-System.git
cd AI-Cortex-Memory-System

# 2. 建立並啟動虛擬環境
python -m venv venv
.\venv\Scripts\activate  # Windows

# 3. 安裝依賴與下載模型
pip install -r requirements.txt
ollama pull bge-m3
```

### 3. 啟動服務
1.  **啟動資料庫**：`docker compose up -d`
2.  **一鍵啟動** (Windows)：雙擊 `launch_services.bat`。

---

## 🏗 主要組件

### 📊 3D 視覺化儀表板 (Dashboard)
- 檔案: [dashboard.py](dashboard.py)
- **3D 記憶圖譜**：即時觀察記憶節點之間的關聯與聚類。
- **時間線檢視**：回溯記憶形成的歷史軌跡。

### 💬 智控對話 (Chat Demo)
- 檔案: [chat.py](chat.py)
- 展示 AI 如何在回答前自動執行「回想」，並在回答後自動進行「強化」。

### 🔌 通用 API 與 MCP
- 資料夾: [api](api) / [cortex_mcp_server.py](cortex_mcp_server.py)
- 讓 Claude Code, Cursor 或任何自製 Agent 都能無縫接軌您的記憶池。

---

## 🔧 串接規範
支援任何具備 HTTP 呼叫能力的 AI。核心循環：
1. `POST /agent/context` (獲取動態背景)
2. 將背景加入您的 LLM Prompt。
3. `POST /agent/store` (存入決策決策)

參考指令規範：[CORTEX_AI_INSTRUCTIONS.md](./CORTEX_AI_INSTRUCTIONS.md)
