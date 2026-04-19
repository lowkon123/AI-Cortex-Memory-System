# Cortex Memory Engine Implementation Plan / 皮層記憶引擎實施計劃

## Overview / 概覽
Design and implement a production-grade, hierarchical AI memory system. This plan now includes advanced features like associative graph indexing, neural decay, and adaptive zoom.
設計並實現一個生產級、層次化的 AI 記憶系統。本計劃現已納入高級功能，如關聯圖譜索引、神經衰減以及自適應縮放。

## User Review Required / 需要用戶確認

> [!IMPORTANT]
> **Core Strategy / 核心策略**: 
> - **Multi-Language Separation**: `src/en/` and `src/zh_tw/` will contain identical logic but localized comments and docstrings in separate files.
> - **Advanced Innovation**: Includes Graph-based recall and the "Sleep Cycle" (background compression).
> 
> **語言分離**：`src/en/` 和 `src/zh_tw/` 將包含相同的邏輯，但在獨立的文件中提供本地化的註釋和文檔。
> **高級創新**：包含基於圖譜的召回和「睡眠周期」（後台壓縮）機制。

## Phase 1: Standard Architecture / 第一階段：標準架構
(All modules exist in both `_en.py` and `_zh.py` versions)

### 1. Storage & Indexing / 存儲與索引
- **memory_store**: Persistence of raw memory objects. / 原始記憶對象持久化。
- **memory_index**: PostgreSQL metadata management. / PostgreSQL 元數據管理。
- **memory_vector**: FAISS vector search integration. / FAISS 向量搜索集成。

### 2. Logic & Ranking / 邏輯與排序
- **memory_ranker**: Multi-factor scoring (Sim + Recency + Imp + Freq). / 多因子評分。
- **memory_forgetting**: Neural decay and pruning logic. / 神經衰減與剪枝邏輯。

### 3. Hierarchy & Context / 分層與上下文
- **memory_zoom**: Progressive depth control (L0/L1/L2). / 漸進式深度控制。
- **memory_compressor**: LLM-driven hierarchical summarization. / LLM 驅動的分層總結。
- **context_builder**: Token-efficient context injection. / Token 高效上下文注入。

## Phase 2: Advanced Innovation / 第二階段：高級創新功能
(Designed for "Wows" and industry-leading performance)

### 4. Associative Memory / 聯想記憶
#### [NEW] [memory_graph.py](file:///d:/Projects/Antigravity/src/memory_graph.py)
Implements an entity-relation graph to allow "jump-recall" between related nodes.
實現實體關係圖譜，允許在相關節點間進行「跳轉召回」。

### 5. Neural Dynamics / 神經動力學
#### [NEW] [memory_scheduler.py](file:///d:/Projects/Antigravity/src/memory_scheduler.py)
Manages the "Sleep Cycle" for background optimization and cold-data offloading.
管理「睡眠周期」，用於後台優化和冷數據轉存。

### 6. Reinforcement Feedback / 強化反饋
#### [NEW] [memory_feedback.py](file:///d:/Projects/Antigravity/src/memory_feedback.py)
Tracks which memories successfully solved LLM tasks and boosts their rank.
追踪哪些記憶成功解決了 LLM 任務並提升其排名。

## Deployment & Verification / 部署與驗證
- **Docker**: Provide `docker-compose.yml` for Postgres & PgVector. / 提供 Postgres 和 PgVector 的 `docker-compose.yml`。
- **Testing**: Bilingual test suite in `tests/`. / `tests/` 中的雙語測試套件。
