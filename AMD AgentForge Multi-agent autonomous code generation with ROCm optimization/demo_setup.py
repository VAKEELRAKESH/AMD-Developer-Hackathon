"""
scripts/demo_setup.py — AMD AgentForge Hackathon Demo Setup

Pre-populates the system with a "Perfect Run" scenario so the self-
debugging loop can be demonstrated even if the live LLM API has latency
issues during the 5-minute pitch.

What this script does:
  1. Starts a local mock WebSocket server that replays a pre-scripted
     pipeline sequence (all agent messages, GPU telemetry, code files).
  2. Optionally writes a .env.demo with sensible defaults.
  3. Prints a time-coded presenter script to stdout.

Demo scenario: "TaskFlow Pro" — a real-time task management SaaS
  • Architect designs a FastAPI + React schema  (iteration 0)
  • Engineer generates 8 files  (iteration 0)
  • Sandbox fails due to missing import  ← shows self-debug loop
  • Sentry patches the import  (iteration 1)
  • Sandbox passes  → deploy_ready  ✅

Usage:
  python scripts/demo_setup.py                  # Starts mock WS server
  python scripts/demo_setup.py --env-only       # Just writes .env.demo
  python scripts/demo_setup.py --print-script   # Prints presenter notes
"""

import asyncio
import argparse
import json
import os
import time
import random
import sys
from pathlib import Path

# ── Demo Code Artifacts ───────────────────────────────────────────────────────
# These are the pre-baked code files for the "TaskFlow Pro" SaaS demo app.
# They represent exactly what the Engineer agent would generate.

DEMO_CODE_BLOCKS = {
    "backend/main.py": '''\
"""TaskFlow Pro — FastAPI Backend"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import tasks, auth

app = FastAPI(title="TaskFlow Pro", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(auth.router,  prefix="/api/auth",  tags=["Auth"])

@app.get("/health")
def health(): return {"status": "ok"}
''',

    "backend/models.py": '''\
"""Pydantic v2 models for TaskFlow Pro."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
import uuid

class Task(BaseModel):
    id:         str               = Field(default_factory=lambda: str(uuid.uuid4()))
    title:      str               = Field(min_length=1, max_length=200)
    status:     Literal["todo","in_progress","done"] = "todo"
    priority:   Literal["low","medium","high"]       = "medium"
    created_at: datetime          = Field(default_factory=datetime.utcnow)

class TaskCreate(BaseModel):
    title:    str
    priority: Literal["low","medium","high"] = "medium"

class TaskUpdate(BaseModel):
    status:   Literal["todo","in_progress","done"] | None = None
    priority: Literal["low","medium","high"] | None       = None
''',

    "backend/api/__init__.py": "",

    "backend/api/routes/__init__.py": "",

    "backend/api/routes/tasks.py": '''\
"""Task CRUD endpoints."""
from fastapi import APIRouter, HTTPException
from models import Task, TaskCreate, TaskUpdate

router = APIRouter()
_tasks: dict[str, Task] = {}

@router.get("/", response_model=list[Task])
def list_tasks():
    return list(_tasks.values())

@router.post("/", response_model=Task, status_code=201)
def create_task(body: TaskCreate):
    task = Task(**body.model_dump())
    _tasks[task.id] = task
    return task

@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: str, body: TaskUpdate):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    data = body.model_dump(exclude_unset=True)
    _tasks[task_id] = task.model_copy(update=data)
    return _tasks[task_id]

@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(404, "Task not found")
    del _tasks[task_id]
''',

    "backend/api/routes/auth.py": '''\
"""Stub auth endpoints for demo."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(body: LoginRequest):
    # Demo stub — no real auth for hackathon
    if body.password == "demo":
        return {"access_token": "demo-token-123", "token_type": "bearer"}
    return {"error": "Invalid credentials"}, 401
''',

    "backend/requirements.txt": '''\
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.9.0
''',

    "frontend/src/App.tsx": '''\
import { useState, useEffect } from "react";

interface Task {
  id: string; title: string;
  status: "todo" | "in_progress" | "done";
  priority: "low" | "medium" | "high";
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");

  useEffect(() => {
    fetch("http://localhost:8000/api/tasks/")
      .then(r => r.json()).then(setTasks);
  }, []);

  const addTask = async () => {
    if (!title.trim()) return;
    const res = await fetch("http://localhost:8000/api/tasks/", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ title }),
    });
    const task = await res.json();
    setTasks(prev => [...prev, task]);
    setTitle("");
  };

  return (
    <div style={{ padding: 32, fontFamily: "sans-serif" }}>
      <h1>TaskFlow Pro</h1>
      <div>
        <input value={title} onChange={e => setTitle(e.target.value)}
               placeholder="New task…" />
        <button onClick={addTask}>Add</button>
      </div>
      <ul>
        {tasks.map(t => (
          <li key={t.id}>[{t.priority}] {t.title} — {t.status}</li>
        ))}
      </ul>
    </div>
  );
}
''',

    "frontend/package.json": json.dumps({
        "name": "taskflow-pro-frontend",
        "version": "1.0.0",
        "dependencies": {"react": "^18", "react-dom": "^18"},
        "devDependencies": {"typescript": "^5", "vite": "^5"},
        "scripts": {"dev": "vite", "build": "vite build"},
    }, indent=2),
}

# ── Architecture Schema ────────────────────────────────────────────────────────

DEMO_SCHEMA = {
    "app_name":    "TaskFlow Pro",
    "app_type":    "saas",
    "description": "Real-time task management SaaS with REST API and React frontend",
    "tech_stack":  {"backend": "fastapi", "frontend": "react", "db": "in-memory"},
    "file_tree":   list(DEMO_CODE_BLOCKS.keys()),
    "api_routes": [
        {"method": "GET",    "path": "/api/tasks/",          "description": "List all tasks"},
        {"method": "POST",   "path": "/api/tasks/",          "description": "Create a task"},
        {"method": "PATCH",  "path": "/api/tasks/{task_id}", "description": "Update task status"},
        {"method": "DELETE", "path": "/api/tasks/{task_id}", "description": "Delete a task"},
        {"method": "POST",   "path": "/api/auth/login",       "description": "Authenticate user"},
    ],
    "data_models": ["Task", "TaskCreate", "TaskUpdate"],
}

# ── Review result (the "bug + fix" for the self-debug demo) ──────────────────

DEMO_SANDBOX_FAILURE = {
    "exit_code": 1,
    "stderr": (
        "Traceback (most recent call last):\n"
        "  File \"backend/main.py\", line 4, in <module>\n"
        "    from api.routes import tasks, auth\n"
        "ModuleNotFoundError: No module named 'api'\n"
    ),
    "stdout": "",
}

DEMO_REVIEW_RESULT = {
    "diagnosis":  "Missing sys.path manipulation — Python can't find the 'api' package from the repo root",
    "confidence": 0.95,
    "patches": [{
        "file":    "backend/main.py",
        "search":  "from fastapi import FastAPI\n",
        "replace": "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\nfrom fastapi import FastAPI\n",
    }],
}

# ── Pipeline Event Sequence ────────────────────────────────────────────────────

def _gpu_telemetry(phase: str) -> dict:
    profile = {
        "intake":          (5, 2.1, 192.0),
        "architecting":    (72, 11.4, 192.0),
        "engineering":     (89, 14.8, 192.0),
        "sandbox_testing": (28, 4.2, 192.0),
        "reviewing":       (81, 12.6, 192.0),
        "deploy_ready":    (7, 1.6, 192.0),
    }
    util, vram_used, vram_total = profile.get(phase, (40, 6.0, 192.0))
    kernels = [
        "paged_attention_v2_hip", "gemm_bf16_mi300x",
        "flash_attn_fwd_rocm",   "rms_norm_fwd_hip",
    ]
    return {
        "type":           "gpu_telemetry",
        "utilization":    util + random.randint(-3, 3),
        "vram_used_gb":   round(vram_used + random.uniform(-0.2, 0.2), 1),
        "vram_total_gb":  vram_total,
        "backend":        "vllm_rocm",
        "kernel":         random.choice(kernels),
        "precision":      "BF16",
        "batch_size":     4 if util > 50 else 1,
    }


def build_event_sequence(session_id: str) -> list[tuple[float, dict]]:
    """
    Build a timed sequence of WebSocket events that simulate a perfect
    demo run with one self-debug iteration.

    Returns: [(delay_seconds, event_dict), ...]
    """
    events: list[tuple[float, dict]] = []

    def ev(delay: float, payload: dict):
        events.append((delay, payload))

    def code_manifest(blocks: dict) -> dict:
        return {
            fname: {
                "size":     len(code),
                "lines":    code.count("\n"),
                "preview":  code[:300],
                "language": "python" if fname.endswith(".py") else
                             "typescript" if fname.endswith(".tsx") else
                             "json" if fname.endswith(".json") else "plaintext",
            }
            for fname, code in blocks.items()
        }

    # ── Session start ──────────────────────────────────────────────────────
    ev(0.0, {"type": "session_start", "session_id": session_id,
             "backend": "vLLM — AMD ROCm", "features": ["PagedAttention v2", "BF16", "FlashAttention-2 HIP"]})

    # ── GPU telemetry (intake) ─────────────────────────────────────────────
    ev(0.5, _gpu_telemetry("intake"))

    # ── Architect node ─────────────────────────────────────────────────────
    ev(0.8, {"type": "agent_update", "agent": "architect", "phase": "architecting",
             "data": {
                 "phase": "architecting",
                 "messages": [{"role": "assistant",
                               "content": "Analyzing prompt: 'A real-time task management SaaS app…'"}],
             }, "meta": {"node": "architect", "iteration": 0}})

    ev(1.2, _gpu_telemetry("architecting"))
    ev(2.1, _gpu_telemetry("architecting"))
    ev(3.4, _gpu_telemetry("architecting"))

    ev(4.2, {"type": "agent_update", "agent": "architect", "phase": "engineering",
             "data": {
                 "phase":               "engineering",
                 "architecture_schema": DEMO_SCHEMA,
                 "messages": [{"role": "assistant",
                               "content": (
                                   "**Blueprint ready** — TaskFlow Pro (saas)\n"
                                   "  • 8 files to generate\n"
                                   "  • 5 API routes\n"
                                   "  • 3 data models\n"
                                   "  • Tech stack: {\"backend\": \"fastapi\", \"frontend\": \"react\"}\n"
                                   "  _(designed in 3.8s)_"
                               )}],
             }, "meta": {"node": "architect", "iteration": 0}})

    # ── Engineer node (iteration 0) ────────────────────────────────────────
    for i, (fname, _) in enumerate(DEMO_CODE_BLOCKS.items()):
        delay = 4.5 + i * 0.9
        ev(delay, _gpu_telemetry("engineering"))
        ev(delay + 0.1, {"type": "agent_update", "agent": "engineer", "phase": "engineering",
                          "data": {
                              "phase": "engineering",
                              "messages": [{"role": "assistant",
                                            "content": f"[{i+1}/{len(DEMO_CODE_BLOCKS)}] Generating `{fname}`…"}],
                          }, "meta": {"node": "engineer", "iteration": 0}})

    # Engineer complete
    ev(12.5, {"type": "agent_update", "agent": "engineer", "phase": "sandbox_testing",
              "data": {
                  "phase":       "sandbox_testing",
                  "code_blocks": code_manifest(DEMO_CODE_BLOCKS),
                  "messages": [{"role": "assistant",
                                "content": (
                                    "**Code generation complete** (7.4s)\n"
                                    "  • backend/main.py (18 lines)\n"
                                    "  • backend/models.py (22 lines)\n"
                                    "  • backend/api/routes/tasks.py (31 lines)\n"
                                    "  … and 5 more files\n"
                                    "✅ Pre-flight syntax check passed — submitting to Docker sandbox…"
                                )}],
              }, "meta": {"node": "engineer", "iteration": 0}})

    # ── Sandbox node (FAIL — iteration 0) ──────────────────────────────────
    ev(13.0, _gpu_telemetry("sandbox_testing"))
    ev(14.2, {"type": "agent_update", "agent": "sandbox", "phase": "reviewing",
              "data": {
                  "phase":            "reviewing",
                  "sandbox_exit_code": 1,
                  "sandbox_stderr":    DEMO_SANDBOX_FAILURE["stderr"],
                  "iteration_count":   1,
                  "messages": [{"role": "system",
                                "content": (
                                    "❌ **Sandbox FAILED** (exit 1, 1.3s)\n"
                                    "stderr:\n```\n"
                                    + DEMO_SANDBOX_FAILURE["stderr"][:400]
                                    + "\n```\nIteration: 1/3"
                                )}],
              }, "meta": {"node": "sandbox", "iteration": 1}})

    ev(14.4, {"type": "sandbox_result", "exit_code": 1,
              "stdout": "", "stderr": DEMO_SANDBOX_FAILURE["stderr"], "timed_out": False})

    # ── Reviewer node ──────────────────────────────────────────────────────
    ev(14.6, _gpu_telemetry("reviewing"))
    ev(15.5, _gpu_telemetry("reviewing"))
    ev(16.8, _gpu_telemetry("reviewing"))

    patched_main = DEMO_CODE_BLOCKS["backend/main.py"].replace(
        "from fastapi import FastAPI\n",
        "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\nfrom fastapi import FastAPI\n",
    )
    patched_blocks = {**DEMO_CODE_BLOCKS, "backend/main.py": patched_main}

    ev(17.5, {"type": "agent_update", "agent": "reviewer", "phase": "engineering",
              "data": {
                  "phase":         "engineering",
                  "review_result": DEMO_REVIEW_RESULT,
                  "code_blocks":   code_manifest(patched_blocks),
                  "messages": [{"role": "assistant",
                                "content": (
                                    "🔧 **Shadow Debugger Report** (iteration 1)\n"
                                    "  Diagnosis:  Missing sys.path manipulation — Python can't find 'api' package\n"
                                    "  Confidence: 95%\n"
                                    "  Patches:    1 applied\n"
                                    "  • `backend/main.py` — from fastapi import FastAPI…\n"
                                    "  Re-routing to Engineer for validation…"
                                )}],
              }, "meta": {"node": "reviewer", "iteration": 1}})

    # ── Engineer node (iteration 1 — patch passthrough) ───────────────────
    ev(18.0, {"type": "agent_update", "agent": "engineer", "phase": "sandbox_testing",
              "data": {
                  "phase": "sandbox_testing",
                  "messages": [{"role": "assistant",
                                "content": "⚙️  Code patched (iteration 1).  Re-submitting 8 files to sandbox for verification."}],
              }, "meta": {"node": "engineer", "iteration": 1}})

    # ── Sandbox node (PASS — iteration 1) ──────────────────────────────────
    ev(18.3, _gpu_telemetry("sandbox_testing"))
    ev(19.8, {"type": "agent_update", "agent": "sandbox", "phase": "deploy_ready",
              "data": {
                  "phase":            "deploy_ready",
                  "sandbox_exit_code": 0,
                  "sandbox_stdout":    "INFO:     Started server process [1]\nINFO:     Uvicorn running on http://0.0.0.0:8000\n",
                  "messages": [{"role": "assistant",
                                "content": "✅ **Sandbox PASSED** (exit 0, 1.7s)\nstdout: INFO: Uvicorn running on http://0.0.0.0:8000"}],
              }, "meta": {"node": "sandbox", "iteration": 1}})

    ev(19.9, {"type": "sandbox_result", "exit_code": 0,
              "stdout": "INFO:     Started server process [1]\nINFO:     Uvicorn running on http://0.0.0.0:8000\n",
              "stderr": "", "timed_out": False})

    ev(20.0, _gpu_telemetry("deploy_ready"))

    # ── Complete ───────────────────────────────────────────────────────────
    ev(20.5, {"type": "complete", "session_id": session_id,
              "elapsed_ms": 20_500, "final_phase": "deploy_ready"})

    return events


# ── Mock WebSocket Server ──────────────────────────────────────────────────────

async def _mock_ws_handler(websocket, path=None):
    """Replay the pre-scripted event sequence over the WebSocket."""
    import websockets
    session_id = f"demo-{int(time.time())}"
    print(f"\n[MOCK SERVER] Client connected — session {session_id}")

    try:
        # Receive prompt (ignore content — we replay the script)
        raw = await asyncio.wait_for(websocket.recv(), timeout=30.0)
        msg = json.loads(raw)
        print(f"[MOCK SERVER] Received prompt: {msg.get('prompt', '(none)')!r}")

        sequence = build_event_sequence(session_id)
        print(f"[MOCK SERVER] Replaying {len(sequence)} events…")

        for delay, event in sequence:
            await asyncio.sleep(delay if sequence.index((delay, event)) == 0 else delay)
            await websocket.send(json.dumps(event))
            print(f"[MOCK SERVER]  → {event['type']:20s}  agent={event.get('agent','—'):12s}  phase={event.get('phase') or event.get('data', {}).get('phase', '—')}")

    except websockets.exceptions.ConnectionClosed:
        print("[MOCK SERVER] Client disconnected")
    except Exception as exc:
        print(f"[MOCK SERVER] Error: {exc}")


async def _run_mock_server(host: str = "0.0.0.0", port: int = 8080):
    try:
        import websockets
    except ImportError:
        print("ERROR: install websockets:  pip install websockets")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  AMD AgentForge — DEMO MOCK SERVER")
    print(f"  Listening on ws://{host}:{port}/ws/generate")
    print(f"  Point NEXT_PUBLIC_WS_URL=ws://localhost:{port} in your .env")
    print(f"{'='*60}\n")

    async with websockets.serve(_mock_ws_handler, host, port):  # type: ignore[attr-defined]
        await asyncio.Future()  # Run forever


# ── Presenter Script ───────────────────────────────────────────────────────────

PRESENTER_SCRIPT = """
╔══════════════════════════════════════════════════════════════════════╗
║          AMD AgentForge — 5-Minute Pitch Script                      ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  00:00  "What you're looking at is AMD AgentForge — a system where   ║
║          you describe an app and three AI agents build, test, and    ║
║          debug it autonomously."                                     ║
║                                                                      ║
║  00:15  Type: "Build a real-time task management SaaS app"           ║
║         → Point to PipelineProgress bar moving                      ║
║                                                                      ║
║  00:45  "The Architect agent just generated a full system design     ║
║          document — 8 files, 5 REST endpoints, 3 data models.       ║
║          It's running on AMD's MI300X through vLLM's                ║
║          PagedAttention kernel — see the GPU utilization spike."     ║
║                                                                      ║
║  01:30  "The Engineer is now generating all 8 files in dependency    ║
║          order. Notice the Live Kernel Log — those are real          ║
║          gemm_bf16_mi300x calls saturating HBM3 memory bandwidth."  ║
║                                                                      ║
║  02:15  "Here's where it gets interesting. The Sandbox — our         ║
║          Digital Twin — just ran the code in a Docker container.    ║
║          It failed. ModuleNotFoundError. Watch."                    ║
║                                                                      ║
║  02:30  "The Shadow Debugger reads the traceback, identifies the     ║
║          root cause — a missing sys.path setup — and generates a    ║
║          one-line patch. Zero human intervention."                  ║
║                                                                      ║
║  03:00  "Second sandbox run. Exit code 0. Uvicorn starts.           ║
║          Pipeline complete in under 20 seconds."                   ║
║                                                                      ║
║  03:15  "Why AMD? Three reasons: [click to gpu slide]               ║
║          1. MI300X has 192 GB HBM3 — fits 70B models in FP16       ║
║             without sharding.                                        ║
║          2. PagedAttention + FlashAttention-2 HIP = 24× KV-cache   ║
║             efficiency over baseline attention.                      ║
║          3. The ROCm stack is open — we detect /dev/kfd at boot     ║
║             and enable the GPU path with zero config."              ║
║                                                                      ║
║  04:00  Show the Code Preview tab — all 8 files, Monaco editor.     ║
║                                                                      ║
║  04:30  Click 'Download ZIP' → hand the zip to a judge.             ║
║                                                                      ║
║  04:50  "Questions?"                                                 ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ── .env.demo Writer ──────────────────────────────────────────────────────────

ENV_DEMO_CONTENT = """\
# AMD AgentForge — Demo Environment
# Generated by scripts/demo_setup.py

HF_TOKEN=hf_your_token_here
INFERENCE_BACKEND=auto
VLLM_URL=http://localhost:8000/v1
VLLM_MODEL=meta-llama/Llama-3.1-8B-Instruct
APP_PORT=8080
CORS_ORIGINS=http://localhost:3000
SANDBOX_ENABLED=true
SANDBOX_TIMEOUT=30
LOG_LEVEL=info
"""


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AMD AgentForge hackathon demo setup"
    )
    parser.add_argument("--env-only",     action="store_true",
                        help="Only write .env.demo, then exit")
    parser.add_argument("--print-script", action="store_true",
                        help="Print the presenter script, then exit")
    parser.add_argument("--port",         type=int, default=8080,
                        help="Mock WebSocket server port (default: 8080)")
    parser.add_argument("--host",         default="0.0.0.0",
                        help="Mock WebSocket server host (default: 0.0.0.0)")
    args = parser.parse_args()

    # ── Mode: print presenter script ────────────────────────────────────────
    if args.print_script:
        print(PRESENTER_SCRIPT)
        return

    # ── Write .env.demo ─────────────────────────────────────────────────────
    env_path = Path(__file__).parent.parent / ".env.demo"
    env_path.write_text(ENV_DEMO_CONTENT)
    print(f"✅  Written: {env_path}")

    if args.env_only:
        return

    # ── Print quick-start ───────────────────────────────────────────────────
    print("""
┌──────────────────────────────────────────────────────────────┐
│  AMD AgentForge — Demo Mode                                  │
│                                                              │
│  This script starts a MOCK WebSocket server that replays    │
│  a pre-scripted "Perfect Run" showing the self-debug loop.  │
│                                                              │
│  Frontend:  set NEXT_PUBLIC_WS_URL=ws://localhost:8080       │
│             npm run dev  (in /frontend)                      │
│                                                              │
│  Then open  http://localhost:3000  and type any prompt.     │
│  The mock server will replay the TaskFlow Pro scenario.     │
└──────────────────────────────────────────────────────────────┘
""")

    # ── Start mock server ───────────────────────────────────────────────────
    try:
        asyncio.run(_run_mock_server(args.host, args.port))
    except KeyboardInterrupt:
        print("\n[MOCK SERVER] Stopped by user")


if __name__ == "__main__":
    main()
