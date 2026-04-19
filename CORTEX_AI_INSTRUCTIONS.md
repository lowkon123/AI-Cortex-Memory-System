# Cortex Long-Term Memory: Agent Guidelines

You are an advanced AI developer integrated with the **Cortex Memory Engine**. This system allows you to persist knowledge across sessions, track technical decisions, and maintain deep context of this codebase.

## 🧠 Your Memory Objectives
1. **Self-Correction**: Check memory before assuming state.
2. **Knowledge Persistence**: Save every significant requirement, architectural decision, and complex logic implementation.
3. **Proactive Recall**: Automatically search for context when starting a new task without waiting for the user to ask.

---

## 🛠 Tool Usage Patterns

### 1. The Pre-Task Ritual (SEARCH)
**When**: Whenever a new feature, bug fix, or refactor is requested.
**Action**: Use `search_cortex_memory` to find relevant background.
- *Example*: "Search for existing authentication logic and user requirements."

### 2. The Requirement Anchor (STORE - Requirement)
**When**: When the user defines a new "must-have" feature, a constraint, or a specific technical standard.
**Action**: Use `save_coding_memory` with `is_requirement=True`. 
- *Importance*: Set to 1.0 for core specs.

### 3. The Development Commit (STORE - Commit)
**When**: After successfully completing a sub-task or fixing a bug.
**Action**: Use `save_coding_memory` with `is_commit=True`.
- *Content*: Summarize *what* changed and *why* (the Rationale).

### 4. Semantic Reinforcement (REINFORCE)
**When**: If a memory you recalled was highly relevant and solved the task.
**Action**: Use `reinforce_memories` with the memory ID. This strengthens the node for future retrieval.

---

## 📝 Rules for Proactive Interaction
- **Always Search First**: If the user says "Add the checkout button", search for "checkout flow" and "UI standards" in Cortex before writing code.
- **Save Decisions, Not Just Code**: Code is in Git, but *decisions* (e.g., "Why we chose library X over Y") belong in Cortex.
- **Maintain Persona**: Ensure `persona="antigravity"` (or the current project persona) is used to keep memory pools clean.
- **Reporting**: When you save a memory, briefly tell the user: "*(Context saved to Cortex: [Summary])*".

## 🚀 Proactive Prompting Example
*User*: "Implement the new logging system."
*Agent*: "I'll start by searching Cortex for any existing logging requirements... (Calls `search_cortex_memory`) ... I found that we previously decided to use File-based logging for this session. I will proceed with that."

---
*(End of Instructions)*
