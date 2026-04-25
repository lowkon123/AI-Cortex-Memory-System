"""Proactive Scanner — Automatic reminders for time-sensitive memories.

Scans the memory store before each conversation to identify upcoming 
events and generates reminder text to inject into the System Prompt.
"""

import json
import httpx
from datetime import datetime


async def scan_upcoming(store, model: str, days_ahead: int = 3,
                         base_url: str = "http://localhost:11434",
                         persona: str = "default") -> list[str]:
    """Scan memory store for time-sensitive memories and generate reminders.

    Args:
        store: MemoryStore instance.
        model: Ollama model name.
        days_ahead: Number of days to look ahead.
        base_url: Ollama API endpoint.
        persona: Current persona name.

    Returns:
        List of reminder strings.
    """
    # Fetch recent memories
    memories = await store.list_all(limit=50)
    # Filter by persona
    memories = [m for m in memories if m.persona == persona]

    if not memories:
        return []

    # Filter for memories containing time-related keywords
    time_keywords = ["tomorrow", "next week", "next month", "appointment", "meeting", "deadline",
                     "due", "reminder", "birthday", "anniversary", "exam", "interview", "trip",
                     "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    time_memories = []
    for m in memories:
        content_lower = m.content.lower()
        if any(kw in content_lower for kw in time_keywords):
            ts = m.created_at.strftime('%Y-%m-%d %H:%M')
            time_memories.append(f"[Recorded at {ts}] {m.summary_l1 or m.content[:80]}")

    if not time_memories:
        return []

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M (%A)')
    memories_text = "\n".join(time_memories[:10])

    prompt = f"""Current time is {now_str}.

Below are memory snippets from the user's past conversations mentioned time-related info:
{memories_text}

Determine if any events are upcoming "Today" or within the "Next {days_ahead} days".
If so, list them as concise reminders (one per line).
If no upcoming events, return an empty array [].

Return ONLY a JSON string array:"""

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
