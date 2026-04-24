<p align="center">
  <img src="https://img.shields.io/badge/AMD-ROCm%20Optimized-ED1C24?style=for-the-badge&logo=amd&logoColor=white" alt="AMD ROCm" />
  <img src="https://img.shields.io/badge/LangGraph-Agent%20Orchestration-4B8BBE?style=for-the-badge" alt="LangGraph" />
  <img src="https://img.shields.io/badge/vLLM-PagedAttention-FF6F00?style=for-the-badge" alt="vLLM" />
  <img src="https://img.shields.io/badge/Docker-Sandboxed-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
</p>

# 🔥 AMD AgentForge

**Autonomous multi-agent system that converts natural language prompts into deployable full-stack applications — optimized for AMD ROCm GPU acceleration.**

> *"Describe your app in plain English → Get production-ready code in minutes."*

---

## 🏗️ Architecture Overview

AgentForge orchestrates **4 specialized AI agents** through a LangGraph stateful DAG with a bounded self-correction loop:

```
User Prompt
     │
     ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Architect │ ──▶ │ Engineer │ ──▶ │ Sandbox  │
│  Agent    │     │  Agent   │     │ (Docker) │
└──────────┘     └──────────┘     └────┬─────┘
                       ▲               │
                       │          exit_code?
                       │         ╱          ╲
                  ┌─────────┐  fail        pass
                  │Reviewer │◀─╯            │
                  │ (Sentry)│          ┌────▼────┐
                  └─────────┘          │ Deploy  │
                  max 3 retries        │ Ready ✅│
                                       └─────────┘
```

| Agent | Role | Output |
|-------|------|--------|
| **Architect** | Converts NL prompt → structured JSON blueprint | `app_name`, `tech_stack`, `file_tree`, `api_routes`, `data_models` |
| **Engineer** | Generates all source files from the blueprint | Multi-file `{filename: code}` dictionary |
| **Sandbox** | Executes code in ephemeral Docker containers | `exit_code`, `stdout`, `stderr` |
| **Reviewer (Sentry)** | Analyzes failures → targeted diff patches | `diagnosis`, `confidence`, `patches[]` |

The **self-correction loop** (Sandbox → Reviewer → Engineer → Sandbox) runs up to 3 iterations, with failure memory preventing circular fixes.

---

## ⚡ AMD ROCm Optimization

This project is purpose-built for AMD GPU acceleration:

| Feature | Implementation |
|---------|---------------|
| **GPU-Aware Inference Router** | Auto-detects ROCm → CUDA → CPU → API at startup |
| **vLLM + HIP Kernels** | FlashAttention-2 HIP, PagedAttention, continuous batching |
| **Dynamic Quantization** | AWQ/GPTQ auto-selection based on VRAM availability |
| **GPU Resource Manager** | Real-time VRAM monitoring via `rocm-smi`, batch queue scheduling |
| **Fallback Strategy** | Graceful degradation: ROCm → CUDA → llama.cpp → HuggingFace API |

---

## 🚀 Quick Start

### Option A: Free-Tier Mode (No GPU Required)

Uses HuggingFace Inference API — works on any machine:

```bash
# 1. Clone
git clone https://github.com/VAKEELRAKESH/AMD-Developer-Hackathon.git
cd AMD-Developer-Hackathon

# 2. Set your HuggingFace token
echo "HF_TOKEN=hf_your_token_here" > backend/.env

# 3. Launch
docker-compose -f docker-compose.free-tier.yml up --build
```

Open **http://localhost:3000** → describe your app → watch it build.

### Option B: AMD GPU Mode (ROCm)

For AMD Instinct / Radeon PRO GPUs with ROCm 6.x drivers:

```bash
# 1. Clone
git clone https://github.com/VAKEELRAKESH/AMD-Developer-Hackathon.git
cd AMD-Developer-Hackathon

# 2. Configure
cp backend/.env.example backend/.env
# Edit backend/.env → set HF_TOKEN

# 3. Launch (pulls ROCm-optimized vLLM image)
docker-compose up --build
```

### Option C: Local Development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## 📁 Project Structure

```
AMD-Developer-Hackathon/
├── backend/
│   ├── main.py                      # FastAPI entry point + lifespan
│   ├── core/
│   │   ├── config.py                # Pydantic Settings (env-driven)
│   │   ├── agents/
│   │   │   ├── architect.py         # NL → JSON blueprint
│   │   │   ├── engineer.py          # Blueprint → multi-file code
│   │   │   ├── reviewer.py          # Failure analysis + diff patches
│   │   │   └── prompts/             # System prompt templates (Markdown)
│   │   ├── graph/
│   │   │   ├── state.py             # ForgeState TypedDict (LangGraph)
│   │   │   ├── builder.py           # DAG construction + compilation
│   │   │   ├── nodes.py             # Node functions (async)
│   │   │   └── edges.py             # Conditional routing logic
│   │   ├── inference/
│   │   │   ├── router.py            # GPU-aware backend detection
│   │   │   ├── client.py            # Unified async LLM client
│   │   │   └── gpu_manager.py       # VRAM monitoring + batch queue
│   │   └── sandbox/
│   │       └── executor.py          # Docker container executor
│   ├── api/
│   │   ├── routes/                  # REST endpoints
│   │   └── websocket.py             # Real-time pipeline streaming
│   ├── Dockerfile.api               # Lightweight backend image
│   └── Dockerfile.rocm              # AMD ROCm + vLLM image
├── frontend/                        # Next.js 16 + React 19 dashboard
│   └── src/
│       ├── components/              # Monaco editor, terminal, GPU panel
│       └── hooks/                   # WebSocket + state management
├── docker-compose.yml               # Full stack (GPU mode)
├── docker-compose.free-tier.yml     # API-only mode (no GPU)
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Orchestration** | LangGraph `≥0.2.3` | Stateful DAG with conditional edges, built-in state persistence |
| **Inference** | vLLM + ROCm HIP | PagedAttention, continuous batching, AMD-native FlashAttention-2 |
| **Backend** | FastAPI + WebSockets | Async-first, real-time pipeline streaming to frontend |
| **Frontend** | Next.js 16 + React 19 | Monaco code editor, live terminal, GPU telemetry panel |
| **Sandbox** | Docker SDK (ephemeral) | No-network, memory-limited, auto-removed containers |
| **Config** | Pydantic Settings | Type-safe, env-driven, validated at startup |

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info + docs link |
| `WS` | `/ws/generate` | Real-time pipeline streaming (prompt → code) |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/gpu` | Real-time GPU telemetry (VRAM, utilization, batch stats) |
| `GET` | `/api/gpu/log` | Live kernel activity log |
| `GET` | `/docs` | Interactive Swagger UI |

---

## 🔐 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | — | HuggingFace API token (**required** for free-tier mode) |
| `INFERENCE_BACKEND` | `auto` | `auto` \| `vllm_rocm` \| `vllm_cuda` \| `hf_api` \| `llama_cpp` |
| `VLLM_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | Model to load on vLLM server |
| `SANDBOX_ENABLED` | `true` | Enable/disable Docker sandbox execution |
| `SANDBOX_TIMEOUT` | `30` | Sandbox container timeout (seconds) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |

---

## 📄 License

MIT — Built for the [AMD Developer Hackathon](https://amd.com).
