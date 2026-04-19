# Cortex Memory Engine (皮質記憶引擎)

[English Version](./README.md)

這是一個專為 AI 打造的本地長效記憶系統，比起單純的筆記或向量資料庫，它更模仿人類大腦的運作模式。

Cortex 不僅僅是儲存靜態文件，它能對記憶進行：形成、壓縮、召回、強化、鞏固以及遺忘。

核心目標：`在最小化 Context Token 成本的同時，最大化召回內容的實用性`

## 🚀 快速啟動 (Zero to Hero)

即使是剛重灌的電腦，按順序執行以下流程即可完整運行：

### 1. 準備基礎工具
請確保您的電腦已安裝以下軟體：
- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (用於執行資料庫)
- [Ollama](https://ollama.com/download) (用於本地 AI 向量模型)

### 2. 環境設定
打開您的終端機 (Terminal / PowerShell)，執行以下指令：

```bash
# 1. 複製專案
git clone https://github.com/lowkon123/AI-Cortex-Memory-System.git
cd AI-Cortex-Memory-System

# 2. 建立並啟動虛擬環境 (建議)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. 安裝 Python 套件
pip install -r requirements.txt

# 4. 下載向量模型 (非常重要)
ollama pull bge-m3
```

### 3. 啟動服務
1.  **啟動資料庫**：確保 Docker 正在執行，然後輸入：
    ```bash
    docker compose up -d
    ```
2.  **啟動系統** (Windows)：
    直接雙擊執行 `launch_services.bat`。
    
    *或是手動啟動 (全平台)：*
    - API: `python -m uvicorn api.main:app --port 8002`
    - Dashboard: `python dashboard.py`

### 4. 驗證
- **3D 儀表板**: 打開瀏覽器訪問 `http://localhost:8000`
- **API 狀態**: 訪問 `http://localhost:8002/health` 如果顯示 `status: healthy` 即代表成功！

---

## 🏗 主要組件

### Dashboard (儀表板)
- 檔案: [dashboard.py](dashboard.py)
- 具備 3D 記憶圖譜、詳情面板與即時統計功能。

### Chat Demo (對話演示)
- 檔案: [chat.py](chat.py)
- 具備語意召回與自動強化機制的對話展示。

### Reusable API (通用 API)
- 資料夾: [api](api)
- 提供給外部 AI 工具（如 Claude Code）串接的 REST 介面。

---

## 🔧 AI 串接模式

任何外部 AI 都能透過以下循環使用 Cortex：
1. `POST /agent/context` (獲取背景記憶)
2. 將背景加入您的 LLM Prompt。
3. `POST /agent/store` (存入對話結果或開發決策)

參考指南：[CORTEX_AI_INSTRUCTIONS.md (AI 指令規範)](./CORTEX_AI_INSTRUCTIONS.md)
