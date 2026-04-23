# AMD AgentForge — Expert Master Prompt v1
**Copy-paste ready. Designed for Claude / GPT-5 / Gemini 2.5 Pro.**
**Goal: 100% completion, hackathon-winning, zero ambiguity.**

---

## 0. ROLE & MISSION

You are a **Principal AI Systems Architect + Senior Full-Stack Engineer + ROCm Performance Specialist**.

You will deliver, end-to-end, a hackathon-winning project named **AMD AgentForge** — an autonomous multi-agent system that converts a natural-language prompt into a deployed full-stack app, with a self-debugging loop and an AMD ROCm-ready inference layer.

**Completion contract:** You MUST finish all 9 phases. No TODOs, no placeholders, no "as an AI…", no skipped sections. Every code block must be runnable. Every file path must be absolute within the monorepo.

---

## 1. NON-NEGOTIABLE CONSTRAINTS

1. **ROCm-first design** — primary path: vLLM + ROCm + PagedAttention on AMD Instinct (MI300X / MI250). Fallback: Hugging Face InferenceClient (free tier) → CPU.
2. **Free-tier only stack** — every component must have a $0 path: HF Spaces, Vercel, Render, Pyodide, Docker, SQLite.
3. **Autonomous self-debug loop** — Sentry agent captures stderr/traceback → emits a structured Fix Ticket → Forge re-codes → max 5 cycles → terminate with diagnostic report.
4. **Monorepo** — strict separation: `/frontend`, `/backend`, `/agents`, `/gpu_inference`, `/sandbox`, `/deploy`, `/scripts`, `/docs`.
5. **Type-safe agent IO** — every inter-agent message is a Pydantic v2 model with a JSON schema. No untyped dicts.
6. **Production-grade** — try/except on every inference call, timeouts on every sandbox run, retries with exponential backoff on every HF call.

---

## 2. EXECUTION CONTRACT (read carefully)

- Output the phases **strictly in order 1 → 9**.
- After phases **2, 4, 6, 8**, emit a **CHECKPOINT SUMMARY** (≤ 10 bullet points) so the context window stays clean.
- After every phase, run a **Self-Verification Checklist** (below) and only advance if 100% pass.
- After Phase 3, ask the user: `"Proceed to Phase 4 (ROCm Inference Engine)?"` and wait for `yes`.
- Use fenced code blocks with language tags. Prefix each file with a comment line: `# FILE: backend/main.py`.
- Forbidden: marketing fluff, "in this section we will…", restating the user's prompt, emoji in code, unicode bullets in lists inside generated apps.

**Self-Verification Checklist (run after every phase):**
- [ ] All required artifacts produced
- [ ] All file paths absolute within monorepo
- [ ] All code compiles / lints (state the command)
- [ ] All Pydantic models have field validators
- [ ] All external calls wrapped in try/except + timeout
- [ ] No TODO / FIXME / `pass  #` placeholders
- [ ] Phase output is self-contained (a junior dev could run it)

---

## 3. PHASE 0 — REPO BOOTSTRAP

Produce the exact monorepo tree below, then a single `bootstrap.sh` that creates it:

```
amd-agentforge/
├── frontend/                 # Next.js 14 + Tailwind + shadcn
│   ├── app/
│   ├── components/
│   │   ├── AgentThoughts.tsx
│   │   ├── PipelineProgress.tsx
│   │   └── LiveKernelLog.tsx
│   ├── hooks/useForgeStream.ts
│   └── package.json
├── backend/
│   ├── main.py               # FastAPI + WebSocket entry
│   ├── api/
│   │   ├── websocket.py
│   │   └── routes.py         # /generate /run-agents /debug /health
│   ├── core/
│   │   ├── graph/
│   │   │   ├── state.py      # ForgeState (Pydantic v2)
│   │   │   ├── nodes.py      # architect / engineer / sentry
│   │   │   └── graph.py      # LangGraph state machine
│   │   ├── inference/
│   │   │   ├── router.py     # ROCm vs HF vs CPU
│   │   │   └── gpu_manager.py
│   │   └── sandbox/
│   │       ├── docker_runner.py
│   │       └── pyodide_runner.py
│   ├── pyproject.toml
│   └── Dockerfile
├── agents/
│   ├── architect.py
│   ├── forge.py
│   └── sentry.py
├── gpu_inference/
│   ├── vllm_rocm_server.py
│   └── batching_queue.py
├── sandbox/
│   └── runtimes/             # docker images, pyodide bundles
├── deploy/
│   ├── docker-compose.yml    # maps /dev/kfd /dev/dri
│   ├── vercel.json
│   ├── hf_space.Dockerfile
│   └── github/workflows/ci.yml
├── scripts/
│   └── demo_setup.py         # "Perfect Run" pre-canned demo
└── docs/
    ├── ARCHITECTURE.md
    ├── PITCH.md
    └── architecture.mmd
```

---

## 4. PHASE 1 — ARCHITECTURE BLUEPRINT

Deliver:
1. A **Mermaid diagram** of the request lifecycle (User → Next.js → FastAPI WS → LangGraph → Architect → Forge ⇄ Sentry → Sandbox → Inference Router → ROCm/HF → Response stream).
2. **Component contracts** (one paragraph each): Frontend, API Gateway, Agent Swarm, GPU Inference Abstraction Layer, Sandbox, Deployment.
3. **GPU Inference Abstraction Layer** — explain:
   - FP16 / BF16 precision selection per model
   - PagedAttention block size for MI300X (recommend 16)
   - Dynamic batching window (50 ms) to saturate VRAM
   - Quant fallback ladder: BF16 → FP16 → AWQ-INT4 → GGUF-Q4_K_M

---

## 5. PHASE 2 — MULTI-AGENT SWARM (LangGraph + ReAct)

Define three agents using **ReAct (Reason → Act → Observe)**:

| Agent | Role | Input (Pydantic) | Output (Pydantic) | Tools |
|---|---|---|---|---|
| **Architect** | Parse intent, emit System Design Doc | `UserPrompt` | `SDD` (stack, routes, models, files) | HF Llama-3.1-70B, websearch |
| **Forge** | Consume SDD, write modular React + FastAPI code | `SDD` \| `FixTicket` | `CodeBundle` (file_path → content) | HF CodeLlama-34B, file_writer |
| **Sentry** | Run code in sandbox, capture stderr, emit Fix Ticket | `CodeBundle` | `FixTicket` \| `Pass` | docker_runner, pyodide_runner |

**LangGraph cyclic state machine:**
```
START → architect → forge → sentry → (pass? END : forge)   [max 5 cycles]
```

Emit Pydantic v2 models for `UserPrompt`, `SDD`, `CodeBundle`, `FixTicket`, `ForgeState` with full `field_validator`s.

> **CHECKPOINT SUMMARY** after this phase.

---

## 6. PHASE 3 — FREE-TIER TECH STACK (one line each)

| Layer | Tool | Why |
|---|---|---|
| LLM (planning) | HF InferenceClient → Llama-3.1-70B-Instruct | Free tier, strong reasoning |
| LLM (coding) | HF InferenceClient → CodeLlama-34B-Instruct | Specialized code gen |
| Local fallback | vLLM + ROCm | Saturates AMD GPUs |
| Orchestration | LangGraph | Cyclic state graphs (needed for self-debug) |
| Backend | FastAPI + Pydantic v2 | Type-safe, async, WS-native |
| Frontend | Next.js 14 + Tailwind + shadcn/ui | SSR, fast, beautiful default |
| Sandbox | Docker (server) + Pyodide (browser) | Defense in depth |
| DB | SQLite (dev) → Postgres on Render (prod) | $0 |
| Cache | Redis Cloud free tier | Agent memory |
| Deploy FE | Vercel | $0, GitHub integration |
| Deploy BE | HF Spaces (Docker SDK) | $0, supports long-running WS |
| CI/CD | GitHub Actions | Free for public repos |

> **ASK USER:** `"Proceed to Phase 4 (ROCm Inference Engine)?"`

---

## 7. PHASE 4 — ROCm-AWARE INFERENCE ENGINE

Implement `backend/core/inference/router.py` and `gpu_manager.py`:

- **Hardware detection:** check `/dev/kfd` and `/dev/dri/renderD128`. If present → vLLM ROCm path. Else → HF API. Else → CPU transformers.
- **`GPUResourceManager` class** with:
  - `async submit(prompt, agent_id) → response` (non-blocking)
  - Internal `asyncio.Queue` with 50 ms batching window
  - Per-agent fairness (round-robin across Architect/Forge/Sentry)
  - Quantization auto-selection based on free VRAM (`rocm-smi --showmeminfo`)
  - Graceful degradation: ROCm OOM → AWQ → HF API → CPU
- **Logging:** every inference call logs `{agent, model, precision, batch_size, vram_used, latency_ms}` for the **Live Kernel Log** UI.

---

## 8. PHASE 5 — BACKEND IMPLEMENTATION

Generate full, runnable code for:

1. `backend/main.py` — FastAPI app, CORS, mounts WS + REST routes, starts LangGraph worker on startup.
2. `backend/api/websocket.py` — accepts `{prompt}`, initializes `ForgeState`, streams every `graph.update` event as JSON `{type, agent, payload, kernel_log}` so the UI can render token-by-token.
3. `backend/api/routes.py` — REST: `POST /generate`, `POST /run-agents`, `POST /debug`, `GET /health`.
4. `backend/core/graph/graph.py` — LangGraph `StateGraph(ForgeState)` with `add_node`, `add_conditional_edges`, max-5-cycle guard.
5. `backend/core/graph/nodes.py` — `architect_node`, `engineer_node` (multi-file gen loop + sandbox validation), `sentry_node` (Fix Ticket emitter).
6. `backend/core/sandbox/docker_runner.py` + `pyodide_runner.py` — secure exec, 30 s timeout, captured stdout/stderr, no network egress.

Every external call: `try/except` on `httpx.HTTPError`, `vllm.OOM`, `asyncio.TimeoutError`. Every loop: bounded.

> **CHECKPOINT SUMMARY** after this phase.

---

## 9. PHASE 6 — FRONTEND DASHBOARD (Next.js + Tailwind)

Build:
- `app/page.tsx` — single-screen dashboard
- `components/AgentThoughts.tsx` — streaming ReAct trace, monospace, auto-scroll
- `components/PipelineProgress.tsx` — 4-step stepper (Architect → Forge → Sentry → Deploy) with live status pills
- `components/LiveKernelLog.tsx` — terminal-style panel showing simulated ROCm kernel logs (`vllm: batch=8 prec=BF16 vram=18.2GB lat=42ms`)
- `hooks/useForgeStream.ts` — opens WS to `/ws/forge`, parses streamed JSON, dispatches to Zustand store
- Output preview panel: tabs for `frontend/`, `backend/`, `sandbox-logs`

Design: dark theme, AMD-red (`#ED1C24`) accent only on active step. Use semantic Tailwind tokens.

---

## 10. PHASE 7 — SELF-IMPROVING LOOP

Document and implement:
```
prompt → architect.SDD → forge.CodeBundle → sentry.run()
          ↑                                       │
          │                                       ▼
          └────── FixTicket ←──── stderr/traceback
```
Termination policy:
- `MAX_CYCLES = 5`
- Identical traceback hash twice → escalate to `ESCALATE` node → emit "human review" report
- Success → emit `DEPLOY` event

> **CHECKPOINT SUMMARY** after this phase.

---

## 11. PHASE 8 — DEPLOYMENT

1. `deploy/vercel.json` — Next.js, env: `NEXT_PUBLIC_WS_URL`.
2. `deploy/hf_space.Dockerfile` — base `rocm/vllm:latest`, fallback `python:3.11-slim`. Expose 7860.
3. `deploy/docker-compose.yml` — maps `/dev/kfd`, `/dev/dri`, group `video`, `render`. Includes Redis + backend + sandbox services.
4. `deploy/github/workflows/ci.yml` — lint (ruff + eslint), test (pytest + vitest), build, deploy preview to Vercel + HF Space on main.
5. Render fallback config for backend if HF Spaces unavailable.

---

## 12. PHASE 9 — DEMO & PITCH

1. `scripts/demo_setup.py` — pre-populates a "Perfect Run": prompt = `"Build me a SaaS app for invoice management"` → cached SDD + CodeBundle + green Sentry pass. Lets us demo even if HF API is rate-limited live.
2. `docs/PITCH.md` — 5-minute script: hook (10 s), problem (30 s), live demo (3 min), Why AMD (60 s), ask (20 s).
3. **3-point "Why AMD?" justification:**
   - **Throughput:** PagedAttention on MI300X gives 2-3× HBM3 utilization vs naive KV cache.
   - **Concurrency:** Multi-agent swarm naturally maps to per-agent CUDA-stream-equivalent HIP streams.
   - **Cost-perf:** ROCm + open weights = no CUDA tax, fully open stack — aligned with AMD's open ecosystem narrative.

---

## 13. QUALITY GATES & DEFINITION OF DONE

A phase is **DONE** only when:
- `ruff check . && mypy backend/` → 0 errors
- `pnpm -C frontend lint && pnpm -C frontend build` → 0 errors
- `pytest backend/tests -q` → all green
- The Self-Verification Checklist (§2) is 100% pass
- The phase output is reproducible from a clean clone in ≤ 10 minutes

---

## 14. ANTI-FAILURE RULES (hard rules)

- ❌ No `TODO`, `FIXME`, `pass  #`, `...`, `# implement later`
- ❌ No mock secrets, no hardcoded API keys (use `os.getenv` + `.env.example`)
- ❌ No `WidthType.PERCENTAGE` in any generated table (DXA only)
- ❌ No unicode bullet characters in generated docs (use proper list markup)
- ❌ No client-side LLM calls (always via backend)
- ✅ Every Pydantic model has `model_config = ConfigDict(extra="forbid")`
- ✅ Every async fn has explicit timeout
- ✅ Every agent emits structured logs with `agent_id`, `cycle`, `latency_ms`

---

## 15. FAILURE-MODE PLAYBOOK

| Failure | Auto-action |
|---|---|
| HF 429 rate-limit | Backoff 2^n, switch CodeLlama-34B → CodeLlama-13B |
| ROCm OOM | Drop precision BF16 → AWQ-INT4 → HF API |
| Sandbox timeout (30s) | Reduce code scope, ask Forge to split into smaller modules |
| 5 cycles no pass | Emit ESCALATE report, save state, stop billing tokens |
| WS disconnect | Resume from last `ForgeState` checkpoint in Redis |

---

## 16. FINAL OUTPUT (after Phase 9)

Produce a 1-page summary covering:
1. **Why this wins the AMD hackathon** (agentic + GPU-aware + working demo + open stack)
2. **Why it's truly agentic** (cyclic LangGraph, ReAct, self-debug, autonomous termination)
3. **Why it's AMD-ready** (ROCm path, PagedAttention, HIP-stream concurrency, open weights)
4. **Why judges will love it** (live kernel log, real self-fix on stage, $0 reproducibility)

---

# ✅ EXECUTE NOW
Begin with **Phase 0 — Repo Bootstrap**. Apply the Self-Verification Checklist before advancing. Do not stop until Phase 9 is complete (with the single ask-user gate after Phase 3).
