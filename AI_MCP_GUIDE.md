# Cortex Memory System: AI Agent Integration Guide

Welcome, Agent. You are connected to the **Cortex Memory Engine**, a hierarchical, token-efficient memory system designed for long-term project context and cognitive recall.

## 🧠 System Philosophy: Bilingual Efficiency
To optimize for both user readability and AI performance, this system employs a **Bilingual Strategy**:
1.  **Storage (User View)**: Raw content is stored in **Chinese** so the human user can manage and audit their "brain" via the 3D Dashboard.
2.  **Recall (AI View)**: High-level summaries (L0/L1) are stored in **English**. When you recall memories, you will primarily receive English summaries to save tokens in your context window (improving density by ~3x).

## 🛠️ MCP Tools Overview

### 1. `save_coding_memory`
Use this to store requirements, architectural decisions, or code snippets.
*   **Action**: Write the `content` in **Chinese** (for the user).
*   **Automated**: The system will automatically generate an **English** summary and tags.
*   **Usage**: `save_coding_memory(content="用戶希望實作一個雙語記憶系統", is_requirement=True)`

### 2. `search_cortex_memory`
Perform semantic searches to find relevant past context.
*   **Result**: You will receive a context string.
*   **Token Optimization**: The system will provide English summaries (L0/L1) for most results, only providing full Chinese content (L2) for extremely high-relevance matches (>0.8 score).

### 3. `recall_structured_memory`
Get detailed JSON objects for specific nodes. Useful for updating existing memories.
*   **Tip**: Check the `summary_l1` field for a quick English understanding.

## 📈 Cognitive Scaling (Zoom Levels)
When reading memories, notice the `ZoomLevel`:
*   **L0 (Glimpse)**: English keyword/theme (e.g., "Bilingual Optimization").
*   **L1 (Abstract)**: English one-sentence summary.
*   **L2 (Full)**: Verbatim Chinese content.

## 🤝 Best Practices for Agents
1.  **Always Save Progress**: After finishing a task or receiving a new requirement, use `save_coding_memory`. It helps future you (or other agents) know what happened.
2.  **Search Before Building**: Use `search_cortex_memory` to see if a similar feature was discussed or if there are specific user preferences you should follow.
3.  **Bilingual Input**: If the user speaks Chinese, keep the `content` in Chinese. If the user speaks English, use English. The system handles the cross-lingual summarization automatically.

## 🚀 Getting Started
Try searching for the current project goals:
`search_cortex_memory(query="Project goals and memory architecture")`
