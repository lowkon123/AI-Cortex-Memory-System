import asyncio
import httpx
import msvcrt
import os
import sys
from datetime import datetime
from uuid import UUID, uuid4

from src.memory_feedback import MemoryFeedback
from src.models import MemoryKind, MemoryNode, MemorySource, MemoryStoreConfig, ZoomLevel, utc_now
from src.zh_tw.conflict_detector import check_conflicts
from src.zh_tw.context_builder import ContextBuilder
from src.zh_tw.embedding_provider import OllamaEmbeddingProvider
from src.zh_tw.fact_extractor import extract_facts
from src.zh_tw.memory_ranker import MemoryRanker
from src.zh_tw.memory_store import MemoryStore
from src.zh_tw.memory_summarizer import summarize
from src.zh_tw.memory_vector import MemoryVectorStore
from src.zh_tw.memory_zoom import MemoryZoom
from src.zh_tw.proactive_scanner import scan_upcoming


def choose_model() -> str:
    """Choose an Ollama chat model with keyboard navigation."""
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        resp.raise_for_status()
        all_models = [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:
        print(f"無法取得 Ollama 模型列表: {e}")
        all_models = ["qwen3.5:27b", "gemma4:e2b", "bge-m3:latest"]

    search_query = ""
    filtered_models = all_models.copy()
    current_idx = 0

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("[Cortex Memory Engine] 選擇聊天模型\n")
        print("可直接輸入新模型名稱，或上下鍵選擇既有模型，Enter 確認：")
        print(f"搜尋: {search_query}_\n")

        display_list = []
        if search_query.strip():
            display_list.append(f"建立自訂模型: {search_query.strip()}")
        display_list.extend(filtered_models)

        if not display_list:
            print("  (找不到符合條件的模型)")

        for i, item in enumerate(display_list):
            prefix = "->" if i == current_idx else "  "
            print(f"{prefix} {item}")

        key = msvcrt.getch()
        if key == b"\x03":
            sys.exit(0)
        if key == b"\x08":
            search_query = search_query[:-1]
            filtered_models = [m for m in all_models if search_query.lower() in m.lower()]
            current_idx = 0
            continue
        if key == b"\xe0":
            key = msvcrt.getch()
            if not display_list:
                continue
            if key == b"H":
                current_idx = (current_idx - 1) % len(display_list)
            elif key == b"P":
                current_idx = (current_idx + 1) % len(display_list)
            continue
        if key in (b"\r", b"\n"):
            if not display_list:
                continue
            if search_query.strip() and current_idx == 0:
                return search_query.strip()
            real_idx = current_idx - 1 if search_query.strip() else current_idx
            return filtered_models[real_idx]
        try:
            char = key.decode("utf-8")
            if char.isprintable():
                search_query += char
                filtered_models = [m for m in all_models if search_query.lower() in m.lower()]
                current_idx = 0
        except UnicodeDecodeError:
            pass


def choose_persona() -> str:
    """Choose the persona bucket used for memory retrieval."""
    personas = ["default", "助理", "研究分析", "程式開發"]
    search_query = ""
    current_idx = 0

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("[Cortex Memory Engine] 選擇 persona\n")
        print("可選既有 persona，也可直接輸入新的 persona，Enter 確認：")
        print(f"搜尋: {search_query}_\n")

        filtered = [p for p in personas if not search_query or search_query.lower() in p.lower()]
        display_list = []
        if search_query.strip():
            display_list.append(f"建立新 persona: {search_query.strip()}")
        display_list.extend(filtered)

        if not display_list:
            print("  (找不到符合條件的 persona)")

        for i, item in enumerate(display_list):
            prefix = "->" if i == current_idx else "  "
            print(f"{prefix} {item}")

        key = msvcrt.getch()
        if key == b"\x03":
            sys.exit(0)
        if key == b"\x08":
            search_query = search_query[:-1]
            current_idx = 0
            continue
        if key == b"\xe0":
            key = msvcrt.getch()
            if not display_list:
                continue
            if key == b"H":
                current_idx = (current_idx - 1) % len(display_list)
            elif key == b"P":
                current_idx = (current_idx + 1) % len(display_list)
            continue
        if key in (b"\r", b"\n"):
            if not display_list:
                continue
            if search_query.strip() and current_idx == 0:
                return search_query.strip()
            real_idx = current_idx - 1 if search_query.strip() else current_idx
            return filtered[real_idx]
        try:
            char = key.decode("utf-8")
            if char.isprintable():
                search_query += char
                current_idx = 0
        except UnicodeDecodeError:
            pass


def infer_emotional_weight(sentiment: str | None) -> float:
    mapping = {
        "positive": 0.55,
        "negative": 0.6,
        "mixed": 0.75,
        "neutral": 0.2,
        None: 0.2,
        "": 0.2,
    }
    return mapping.get(sentiment, 0.25)


async def enrich_memory(
    memory: MemoryNode,
    model: str,
    provider: OllamaEmbeddingProvider,
) -> MemoryNode:
    if memory.embedding is None:
        memory.embedding = await provider.get_embedding(memory.content)

    if not memory.concept_tags:
        try:
            facts = await extract_facts(memory.content, model)
        except Exception:
            facts = []
        deduped = []
        for item in facts:
            text = str(item).strip()
            if text and text not in deduped:
                deduped.append(text)
        memory.concept_tags = deduped[:10]

    if not memory.summary_l1 or not memory.summary_l0:
        try:
            l1, l0, sentiment = await summarize(memory.content, model)
        except Exception:
            l1 = memory.content[:80] + ("..." if len(memory.content) > 80 else "")
            l0 = "記憶"
            sentiment = "neutral"
        memory.summary_l1 = memory.summary_l1 or l1
        memory.summary_l0 = memory.summary_l0 or l0
        memory.sentiment = memory.sentiment or sentiment

    if memory.emotional_weight <= 0:
        memory.emotional_weight = infer_emotional_weight(memory.sentiment)

    return memory


def build_memory_system_prompt(persona: str, now_str: str) -> str:
    return f"""你是內建 Cortex Memory Engine 的高效 AI 助理。

目前 persona: {persona}
目前時間: {now_str}

你要這樣使用這套記憶系統：
1. 先讀「Memory Recall Context」，把它當成你的長期與工作記憶，不要逐字重複貼回。
2. 優先使用 activation 高、confidence 高、與當前問題最相關的記憶。
3. 如果不同記憶彼此衝突，先指出不確定性，再選擇較新、較可信、較一致的版本。
4. concept tags 是這則記憶的索引線索，可用來理解主題，不必全部明講。
5. summary_l0 / summary_l1 是壓縮後的思考入口；只有需要細節時才依賴完整內容。
6. 你的目標不是背誦記憶，而是用最少 token 快速整合、推理、回答。
7. 若記憶不足，就誠實說不足，不要假裝從記憶中知道。

回答原則：
- 簡潔、直接、有用。
- 先給結論，再補必要說明。
- 只有在真的有幫助時才提及「根據我記得」這種措辭。
"""


async def generate_chat(chat_model: str, system_prompt: str, user_input: str) -> str:
    prompt = f"{system_prompt}\n\n使用者: {user_input}\n助理:"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": chat_model, "prompt": prompt, "stream": False},
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()["response"]
        except httpx.HTTPError as e:
            return f"[LLM 連線錯誤: 請確認系統已啟動且可使用 {chat_model}。錯誤: {e}]"


def format_recall_block(ranked_memories: list[tuple[MemoryNode, float]], ranker: MemoryRanker) -> str:
    if not ranked_memories:
        return "Memory Recall Context:\n- 目前沒有足夠強的相關記憶。"

    lines = ["Memory Recall Context:"]
    zoom = MemoryZoom()
    for idx, (memory, score) in enumerate(ranked_memories, start=1):
        explanation = ranker.explain_score(
            memory,
            persona=memory.persona,
            query_tags=memory.concept_tags,
        )
        if score >= 0.8:
            zoom.set_level(ZoomLevel.L2_FULL)
        elif score >= 0.55:
            zoom.set_level(ZoomLevel.L1_ABSTRACT)
        else:
            zoom.set_level(ZoomLevel.L0_SUMMARY)

        ts = memory.created_at.strftime("%Y-%m-%d %H:%M")
        tags = ", ".join(memory.concept_tags[:4]) if memory.concept_tags else "no-tags"
        lines.append(
            f"{idx}. score={score:.2f} kind={memory.memory_kind.value} confidence={memory.confidence:.2f} "
            f"reason={explanation['reason']} time={ts} tags={tags}"
        )
        lines.append(f"   {zoom.get_content(memory)}")
    return "\n".join(lines)


async def main():
    selected_model = choose_model()
    selected_persona = choose_persona()
    session_id = uuid4()

    print("正在啟動 Cortex Memory Agent...")

    config = MemoryStoreConfig()
    store = MemoryStore(config)
    await store.connect()
    await store.init_schema()

    v_store = MemoryVectorStore(config)
    v_store.init_index()

    all_memories = await store.list_all(limit=1000)
    persona_memories = [m for m in all_memories if m.persona == selected_persona]
    for memory in persona_memories:
        if memory.embedding:
            v_store.add_memory(memory)

    provider = OllamaEmbeddingProvider(model="bge-m3")
    ranker = MemoryRanker()
    feedback = MemoryFeedback()
    context_builder = ContextBuilder(max_tokens=2400, encoding="cl100k_base")

    print("\n======================================")
    print(" Cortex AI 已啟動")
    print(f" 聊天模型:     [{selected_model}]")
    print(f" 記憶嵌入模型: [{provider.model}]")
    print(f" Persona:      [{selected_persona}]")
    print(f" Session:      [{str(session_id)[:8]}...]")
    print(" 輸入 quit / exit / q 可離開")
    print("======================================\n")

    proactive_reminders = []
    reminders = await scan_upcoming(store, selected_model, persona=selected_persona)
    if reminders:
        proactive_reminders.extend(reminders)

    while True:
        try:
            user_text = input("你: ")
        except EOFError:
            break

        if user_text.lower() in ["quit", "exit", "q"]:
            break
        if not user_text.strip():
            continue

        query_emb = await provider.get_embedding(user_text)
        raw_results = v_store.search(query_emb, k=12)

        candidates = []
        seen_ids = set()
        for mem_id, _dist in raw_results or []:
            memory = await store.get(UUID(mem_id))
            if memory and memory.persona == selected_persona and memory.id not in seen_ids:
                seen_ids.add(memory.id)
                candidates.append(memory)

        ranked_candidates = ranker.rank_memories(
            candidates,
            query_vector=query_emb,
            limit=6,
            persona=selected_persona,
            query_tags=user_text.split(),
            desired_kinds=[MemoryKind.WORKING, MemoryKind.EPISODIC, MemoryKind.SEMANTIC],
        )

        for memory, score in ranked_candidates:
            memory.activation_score = score
            memory.access()
            await store.update(memory)

        recall_block = format_recall_block(ranked_candidates, ranker)
        recall_memories = [memory for memory, _score in ranked_candidates]
        packed_context = context_builder.build_context_with_zoom(ranked_candidates)

        reminder_block = ""
        if proactive_reminders:
            reminder_lines = "\n".join(f"- {item}" for item in proactive_reminders[:5])
            reminder_block = f"\n\nUpcoming Reminder Signals:\n{reminder_lines}"

        system_prompt = (
            build_memory_system_prompt(
                selected_persona,
                datetime.now().strftime("%Y-%m-%d %H:%M (%A)"),
            )
            + "\n\n"
            + recall_block
            + "\n\n"
            + packed_context
            + reminder_block
        )

        response = await generate_chat(selected_model, system_prompt, user_text)
        print(f"AI: {response}\n")

        for memory, _score in ranked_candidates[:3]:
            feedback.reinforce_memory(memory, 0.08)
            memory.updated_at = utc_now()
            await store.update(memory)

        combined_text = f"使用者說: {user_text}\n助理回答: {response}"

        async def process_memory():
            try:
                l1_summary, l0_tag, sentiment = await summarize(combined_text, selected_model)
            except Exception:
                l1_summary = combined_text[:80] + ("..." if len(combined_text) > 80 else "")
                l0_tag = "對話"
                sentiment = "neutral"

            conflict_id = None
            if recall_memories:
                conflict_id = await check_conflicts(combined_text, recall_memories[:3], selected_model)

            new_memory = MemoryNode(
                content=combined_text,
                summary_l1=l1_summary,
                summary_l0=l0_tag,
                importance=0.58,
                sentiment=sentiment,
                emotional_weight=infer_emotional_weight(sentiment),
                session_id=session_id,
                persona=selected_persona,
                source_type=MemorySource.USER,
                memory_kind=MemoryKind.EPISODIC,
                confidence=0.76,
                conflict_with=conflict_id,
            )
            await enrich_memory(new_memory, selected_model, provider)
            new_memory.activation_score = ranker.score_memory(
                new_memory,
                query_vector=query_emb,
                persona=selected_persona,
                query_tags=new_memory.concept_tags,
            )
            await store.insert(new_memory)
            v_store.add_memory(new_memory)

            facts = await extract_facts(combined_text, selected_model)
            for fact_text in facts[:5]:
                fact_text = str(fact_text).strip()
                if not fact_text:
                    continue
                fact_memory = MemoryNode(
                    content=fact_text,
                    summary_l1=fact_text,
                    summary_l0="事實",
                    importance=0.92,
                    sentiment="neutral",
                    emotional_weight=0.15,
                    session_id=session_id,
                    persona=selected_persona,
                    source_type=MemorySource.INFERRED,
                    memory_kind=MemoryKind.SEMANTIC,
                    confidence=0.82,
                )
                await enrich_memory(fact_memory, selected_model, provider)
                fact_memory.activation_score = ranker.score_memory(
                    fact_memory,
                    persona=selected_persona,
                    query_tags=fact_memory.concept_tags,
                )
                await store.insert(fact_memory)
                v_store.add_memory(fact_memory)

        asyncio.create_task(process_memory())

    await store.disconnect()
    print("\nCortex Memory Agent 已關閉。")


if __name__ == "__main__":
    asyncio.run(main())
