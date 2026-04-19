"""主動回想掃描器 — 時間敏感記憶的自動提醒。

在每輪對話前掃描記憶庫，找出即將到來的事件，
並產生提醒文字注入 System Prompt。
"""

import json
import httpx
from datetime import datetime


async def scan_upcoming(store, model: str, days_ahead: int = 3,
                        base_url: str = "http://localhost:11434",
                        persona: str = "default") -> list[str]:
    """掃描記憶庫中的時間敏感記憶，產生提醒。

    Args:
        store: MemoryStore 實例。
        model: Ollama 模型名稱。
        days_ahead: 向前掃描的天數。
        base_url: Ollama API 地址。
        persona: 當前人格名稱。

    Returns:
        提醒字串列表。
    """
    # 取得最近的記憶
    memories = await store.list_all(limit=50)
    # 按 persona 過濾
    memories = [m for m in memories if m.persona == persona]

    if not memories:
        return []

    # 只取含有時間關鍵詞的記憶
    time_keywords = ["明天", "後天", "下週", "下個月", "約會", "會議", "deadline",
                     "截止", "提醒", "生日", "紀念日", "考試", "面試", "旅行",
                     "星期", "禮拜", "月", "號", "日"]
    time_memories = []
    for m in memories:
        if any(kw in m.content for kw in time_keywords):
            ts = m.created_at.strftime('%Y-%m-%d %H:%M')
            time_memories.append(f"[紀錄於 {ts}] {m.summary_l1 or m.content[:80]}")

    if not time_memories:
        return []

    now_str = datetime.now().strftime('%Y年%m月%d日 %H:%M (%A)')
    memories_text = "\n".join(time_memories[:10])

    prompt = f"""現在是 {now_str}。

以下是使用者過去對話中提到時間的記憶片段：
{memories_text}

請判斷其中是否有任何事件在「今天」或「未來 {days_ahead} 天內」即將發生。
如果有，請用簡短的繁體中文列出提醒（每個提醒一行）。
如果沒有即將發生的事件，回傳空陣列 []。

直接回傳 JSON 字串陣列："""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60.0,
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()

            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                raw = "\n".join(lines).strip()

            reminders = json.loads(raw)
            if isinstance(reminders, list):
                return [str(r) for r in reminders if r and str(r).strip()]
            return []

        except Exception:
            return []
