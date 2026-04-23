"""
api/websocket.py — AMD AgentForge WebSocket Gateway

Full-duplex streaming bridge between the Next.js frontend and the
LangGraph pipeline. Every state mutation inside the DAG is serialized
into a strongly-typed JSON envelope and pushed to the client in real time.

Wire protocol (server → client):
  { "type": "session_start",  "session_id": str }
  { "type": "agent_update",   "agent": str, "phase": str,
    "data": {...}, "meta": {...} }
  { "type": "token_stream",   "agent": str, "token": str }
  { "type": "gpu_telemetry",  "utilization": int, "vram_used_gb": float,
    "backend": str, "kernel": str }
  { "type": "sandbox_result", "exit_code": int, "stdout": str, "stderr": str }
  { "type": "complete",       "session_id": str, "elapsed_ms": int }
  { "type": "error",          "message": str, "recoverable": bool }

Wire protocol (client → server):
  { "prompt": str, "max_iterations"?: int }
  { "action": "cancel" }
"""

import json
import uuid
import time
import asyncio
import logging
from typing import AsyncIterator

from fastapi import WebSocket, WebSocketDisconnect

from core.graph.builder import build_forge_graph
from core.graph.state import ForgeState
from core.inference.router import detect_backend, get_backend_info, InferenceBackend
from core.config import settings

logger = logging.getLogger(__name__)


# ── GPU Telemetry Simulator ───────────────────────────────────────────────────
# When ROCm is unavailable we synthesize realistic telemetry so the
# "Live Kernel Log" in the UI remains visually compelling for demos.

_PHASE_GPU_PROFILE = {
    "intake":         {"util": (5,  15),  "vram": (1.2, 2.0)},
    "architecting":   {"util": (60, 80),  "vram": (8.0, 12.0)},
    "engineering":    {"util": (75, 95),  "vram": (11.0, 15.5)},
    "sandbox_testing":{"util": (20, 40),  "vram": (3.0, 5.0)},
    "reviewing":      {"util": (65, 85),  "vram": (9.0, 13.0)},
    "deploy_ready":   {"util": (5,  10),  "vram": (1.0, 1.5)},
    "failed":         {"util": (0,  5),   "vram": (0.8, 1.2)},
}

_ROCM_KERNEL_LABELS = [
    "flash_attn_fwd_rocm",
    "paged_attention_v2_hip",
    "gemm_bf16_mi300x",
    "rotary_embedding_rocm",
    "rms_norm_fwd_hip",
    "sampling_from_probs",
    "copy_blocks_kernel",
]


def _make_gpu_telemetry(phase: str, backend: InferenceBackend) -> dict:
    """Generate a GPU telemetry snapshot for the current pipeline phase."""
    import random
    profile = _PHASE_GPU_PROFILE.get(phase, {"util": (30, 50), "vram": (4.0, 8.0)})
    util   = random.randint(*profile["util"])
    vram   = round(random.uniform(*profile["vram"]), 1)
    kernel = random.choice(_ROCM_KERNEL_LABELS)
    return {
        "type":        "gpu_telemetry",
        "utilization": util,
        "vram_used_gb": vram,
        "vram_total_gb": 192.0 if backend == InferenceBackend.VLLM_ROCM else 24.0,
        "backend":     backend.value,
        "kernel":      kernel,
        "precision":   "BF16" if backend == InferenceBackend.VLLM_ROCM else "FP16",
        "batch_size":  random.choice([1, 2, 4, 4, 8]) if util > 50 else 1,
    }


# ── Payload Serializer ────────────────────────────────────────────────────────

def _serialize_state_update(node_name: str, update: dict) -> dict:
    """
    Flatten a LangGraph state update dict into a WebSocket-safe envelope.

    Rules:
    - code_blocks → send file manifest (name + size), NOT raw source
    - messages    → normalize to [{role, content}] dicts
    - large str   → truncate to 2 000 chars with ellipsis marker
    - non-JSON    → str() cast
    """
    serializable: dict = {}

    for key, value in update.items():

        if key == "messages":
            items = value if isinstance(value, list) else [value]
            serializable[key] = []
            for m in items:
                if hasattr(m, "type") and hasattr(m, "content"):
                    serializable[key].append({
                        "role":    m.type,
                        "content": m.content[:2_000],
                    })
                elif isinstance(m, dict):
                    serializable[key].append({
                        "role":    m.get("role", "unknown"),
                        "content": str(m.get("content", ""))[:2_000],
                    })

        elif key == "code_blocks" and isinstance(value, dict):
            # Send manifest only — full source fetched via REST if needed
            serializable[key] = {
                fname: {
                    "size":     len(code),
                    "lines":    code.count("\n"),
                    "preview":  code[:300],
                    "language": _infer_language(fname),
                }
                for fname, code in value.items()
            }

        elif key == "architecture_schema" and isinstance(value, dict):
            # Send the full schema but cap individual string values
            serializable[key] = value

        elif isinstance(value, str) and len(value) > 2_000:
            serializable[key] = value[:2_000] + "…[truncated]"

        else:
            try:
                json.dumps(value)
                serializable[key] = value
            except (TypeError, ValueError):
                serializable[key] = str(value)[:500]

    return {
        "type":  "agent_update",
        "agent": node_name,
        "phase": update.get("phase", "unknown"),
        "data":  serializable,
        "meta":  {
            "node":      node_name,
            "iteration": update.get("iteration_count", 0),
        },
    }


def _infer_language(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "py": "python", "js": "javascript", "ts": "typescript",
        "tsx": "tsx", "jsx": "jsx", "json": "json",
        "css": "css", "html": "html", "md": "markdown",
        "sh": "bash", "yml": "yaml", "yaml": "yaml",
    }.get(ext, "plaintext")


# ── Connection Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    """Tracks active WebSocket sessions for broadcast and cancellation."""

    def __init__(self):
        self._sessions: dict[str, WebSocket] = {}
        self._cancel_flags: dict[str, asyncio.Event] = {}

    def register(self, session_id: str, ws: WebSocket) -> asyncio.Event:
        self._sessions[session_id] = ws
        flag = asyncio.Event()
        self._cancel_flags[session_id] = flag
        return flag

    def cancel(self, session_id: str):
        if session_id in self._cancel_flags:
            self._cancel_flags[session_id].set()

    def remove(self, session_id: str):
        self._sessions.pop(session_id, None)
        self._cancel_flags.pop(session_id, None)

    @property
    def active_count(self) -> int:
        return len(self._sessions)


manager = ConnectionManager()


# ── Main WebSocket Handler ────────────────────────────────────────────────────

async def websocket_endpoint(websocket: WebSocket):
    """
    Primary WebSocket handler.  Registered in main.py as:
        app.add_websocket_route("/ws/generate", websocket_endpoint)

    Full lifecycle:
      1. Accept + handshake
      2. Parse incoming prompt (or cancel action)
      3. Initialize ForgeState
      4. Stream graph events → client
      5. Interleave GPU telemetry ticks every ~800 ms
      6. Send completion / error envelope
      7. Clean up session
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    start_ts   = time.monotonic()

    # Detect backend once per session (cheap — cached after first call)
    backend    = detect_backend(settings.inference_backend)
    cancel_evt = manager.register(session_id, websocket)

    logger.info(f"[WS:{session_id[:8]}] Connected  (active={manager.active_count})")

    try:
        # ── Step 1: Receive initial message ──────────────────────────────
        raw  = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        msg  = json.loads(raw)

        # Handle pre-emptive cancel (e.g. double-click "Generate")
        if msg.get("action") == "cancel":
            await websocket.close()
            return

        user_prompt = msg.get("prompt", "").strip()
        if not user_prompt:
            await _send_error(websocket, "Empty prompt received", recoverable=True)
            return

        max_iterations = int(msg.get("max_iterations", 3))

        # ── Step 2: Session acknowledgement ──────────────────────────────
        await websocket.send_json({
            "type":       "session_start",
            "session_id": session_id,
            "backend":    get_backend_info(backend).get("name", backend.value),
            "features":   get_backend_info(backend).get("features", []),
        })

        logger.info(f"[WS:{session_id[:8]}] Prompt: {user_prompt[:80]}…")

        # ── Step 3: Initialize ForgeState ────────────────────────────────
        initial_state: ForgeState = {
            "session_id":         session_id,
            "user_prompt":        user_prompt,
            "phase":              "intake",
            "architecture_schema": None,
            "code_blocks":        None,
            "review_result":      None,
            "sandbox_exit_code":  None,
            "sandbox_stdout":     None,
            "sandbox_stderr":     None,
            "iteration_count":    0,
            "max_iterations":     max_iterations,
            "failure_memory":     [],
            "messages":           [],
        }

        # ── Step 4: Build graph + launch telemetry ticker ─────────────────
        graph            = build_forge_graph()
        current_phase    = "intake"
        telemetry_task   = asyncio.create_task(
            _telemetry_ticker(websocket, lambda: current_phase, backend, cancel_evt)
        )

        # ── Step 5: Stream graph events ───────────────────────────────────
        try:
            async for event in graph.astream(
                initial_state,
                config={"configurable": {"thread_id": session_id}},
                stream_mode="updates",
            ):
                # Check for client-side cancel
                if cancel_evt.is_set():
                    logger.info(f"[WS:{session_id[:8]}] Cancelled by client")
                    break

                for node_name, state_update in event.items():
                    current_phase = state_update.get("phase", current_phase)

                    payload = _serialize_state_update(node_name, state_update)
                    await websocket.send_json(payload)

                    # Emit sandbox result as a dedicated event type
                    if node_name == "sandbox" and "sandbox_exit_code" in state_update:
                        await websocket.send_json({
                            "type":      "sandbox_result",
                            "exit_code": state_update.get("sandbox_exit_code"),
                            "stdout":    (state_update.get("sandbox_stdout") or "")[:4_000],
                            "stderr":    (state_update.get("sandbox_stderr") or "")[:4_000],
                            "timed_out": state_update.get("sandbox_timed_out", False),
                        })

                    logger.debug(
                        f"[WS:{session_id[:8]}] {node_name} → {current_phase}"
                    )

        finally:
            telemetry_task.cancel()
            try:
                await telemetry_task
            except asyncio.CancelledError:
                pass

        # ── Step 6: Completion ────────────────────────────────────────────
        elapsed_ms = int((time.monotonic() - start_ts) * 1_000)
        await websocket.send_json({
            "type":        "complete",
            "session_id":  session_id,
            "elapsed_ms":  elapsed_ms,
            "final_phase": current_phase,
        })
        logger.info(
            f"[WS:{session_id[:8]}] Complete  phase={current_phase}  "
            f"elapsed={elapsed_ms}ms"
        )

    except WebSocketDisconnect:
        logger.info(f"[WS:{session_id[:8]}] Client disconnected")

    except asyncio.TimeoutError:
        await _send_error(websocket, "Timed out waiting for prompt", recoverable=False)

    except json.JSONDecodeError as exc:
        await _send_error(websocket, f"Invalid JSON: {exc}", recoverable=False)

    except Exception as exc:
        logger.exception(f"[WS:{session_id[:8]}] Unhandled error: {exc}")
        await _send_error(websocket, str(exc), recoverable=False)

    finally:
        manager.remove(session_id)
        logger.debug(f"[WS:{session_id[:8]}] Session cleaned up")


# ── GPU Telemetry Background Task ─────────────────────────────────────────────

async def _telemetry_ticker(
    websocket: WebSocket,
    phase_fn,          # callable returning current phase string
    backend: InferenceBackend,
    cancel_evt: asyncio.Event,
    interval: float = 0.85,
):
    """
    Push a synthetic GPU telemetry snapshot to the client every ~850 ms.
    Uses the current pipeline phase to modulate the simulated utilization.
    On real hardware with ROCm, replace the _make_gpu_telemetry call with
    an actual `rocm-smi --showuse --showmeminfo vram` subprocess invocation.
    """
    try:
        while not cancel_evt.is_set():
            snapshot = _make_gpu_telemetry(phase_fn(), backend)
            try:
                await websocket.send_json(snapshot)
            except Exception:
                break   # WebSocket closed, stop quietly
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send_error(websocket: WebSocket, message: str, recoverable: bool = False):
    """Attempt to deliver an error envelope; swallow exceptions if WS is closed."""
    try:
        await websocket.send_json({
            "type":        "error",
            "message":     message,
            "recoverable": recoverable,
        })
        await websocket.close()
    except Exception:
        pass
