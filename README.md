# Cortex Memory Engine

[繁體中文版](./README_ZH.md)

A local AI memory system designed to feel closer to human memory than a plain note store or vector database.

Instead of treating memory as static documents, Cortex Memory Engine treats memory as something that can be formed, compressed, recalled, reinforced, consolidated, and forgotten.

The goal is simple: `maximize useful recall while minimizing prompt/context cost`

## 🚀 Quick Start (Zero to Hero)

This is a complete installation process for a fresh system:

### 1. Prerequisites
Ensure you have the following installed:
- [Python 3.10+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (For the database)
- [Ollama](https://ollama.com/download) (For local AI models)

### 2. Environment Setup
Open your Terminal or PowerShell and run:

```bash
# 1. Clone the project
git clone https://github.com/lowkon123/AI-Cortex-Memory-System.git
cd AI-Cortex-Memory-System

# 2. Setup virtual environment (Recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the embedding model (Crucial)
ollama pull bge-m3
```

### 3. Launch Services
1.  **Start Database**: Ensure Docker is running, then run:
    ```bash
    docker compose up -d
    ```
2.  **Launch System** (Windows):
    Simply double-click `launch_services.bat`.
    
    *Or manually (All Platforms):*
    - API: `python -m uvicorn api.main:app --port 8002`
    - Dashboard: `python dashboard.py`

### 4. Verification
- **3D Dashboard**: Visit `http://localhost:8000`
- **API Status**: Visit `http://localhost:8002/health`. If it shows `status: healthy`, you are all set!

---

## 🏗 Main Components

### Dashboard
- File: [dashboard.py](dashboard.py)
- Visual 3D memory graph with detail panels and stats.

### Chat Demo
- File: [chat.py](chat.py)
- Interactive demo with semantic recall and reinforcement.

### Reusable API
- Folder: [api](api)
- REST interface for external AI integrations.

---

## 🔧 Integration Pattern

Any external AI can use Cortex with this loop:
1. `POST /agent/context` (Find background)
2. Call your LLM with the context.
3. `POST /agent/store` (Save new outcomes)

Reference: [CORTEX_AI_INSTRUCTIONS.md](./CORTEX_AI_INSTRUCTIONS.md)
