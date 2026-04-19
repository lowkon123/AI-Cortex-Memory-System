# Cortex AI Memory System - 跨平台串接指南

## 1. 核心資訊
- **MCP Server 路徑**: `./cortex_mcp_server.py` (或是您的絕對路徑)
- **API 埠號**: 8002
- **Dashboard**: `http://localhost:8000`

## 2. 串接 Claude Code (Claude Desktop)
將以下區域貼入 `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "cortex-memory": {
      "command": "python",
      "args": ["/絕對路徑/到/cortex_mcp_server.py"],
      "env": { "PYTHONIOENCODING": "utf-8" }
    }
  }
}
```

## 3. 串接 Codex / Cursor
在 MCP Settings 頁面新增：
- **Name**: `Cortex`
- **Command**: `python [絕對路徑]/cortex_mcp_server.py`

## 4. 常用連動指令
- "請從 Cortex 召回與 [主題] 相關的背景。"
- "將目前的開發進度作為 Commit 存入 Cortex。"
- "檢索 Cortex 中重要性最高的 5 條技術需求。"

## 5. 如何讓 AI 主動使用記憶？
為了讓 AI 「自覺地」在工作前搜尋、工作後存檔，建議進行以下設定：

### 對於 Claude Code (CLI)
在專案根目錄建立或更新 `.clauderules`（或直接在對話中告知）：
> "請閱讀 `CORTEX_AI_INSTRUCTIONS.md` 並嚴格遵守其中的開發規範。在開始任何任務前請先搜尋記憶，在完成後請主動將決策存入 Cortex。"

### 對於 Cursor / Codex
在 **`.cursorrules`** 檔案中加入以下內容：
> "Refer to `CORTEX_AI_INSTRUCTIONS.md` for memory management. Always call `search_cortex_memory` before starting tasks and `save_coding_memory` after changes."

### 對於任何支援 System Prompt 的助理
將 `CORTEX_AI_INSTRUCTIONS.md` 的內容直接貼入其 **Custom Instructions** 或 **System Prompt** 設定中。
