"""
AMD AgentForge — FastAPI Application Entry Point

Starts:
  1. FastAPI app with CORS, REST routes, and the WebSocket gateway
  2. GPUResourceManager background worker (dynamic batching queue)
  3. All inference, graph, and sandbox sub-systems
  4. Structured startup banner (backend + GPU detected)

Deployment variants:
  Local GPU  → INFERENCE_BACKEND=vllm_rocm  docker-compose up
  Free-tier  → INFERENCE_BACKEND=hf_api     docker-compose -f docker-compose.free-tier.yml up
  Dev        → uvicorn main:app --reload --port 8080
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.inference.router import detect_backend, get_backend_info
from core.inference.gpu_manager import gpu_manager
from core.inference.client import InferenceClient

from api.routes.generate import router as generate_router
from api.routes.status   import router as status_router
from api.routes.deploy   import router as deploy_router
from api.websocket        import websocket_endpoint

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = getattr(logging, settings.log_level.upper()),
    format  = "%(asctime)s │ %(name)-32s │ %(levelname)-8s │ %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger("agentforge.main")


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup / shutdown lifecycle.

    Startup order:
      1. Detect inference backend (hardware probe, cached)
      2. Start GPUResourceManager batch worker
      3. Warm up InferenceClient (connects to vLLM / HF API)
      4. Log startup banner
    """
    # ── 1. Backend detection ────────────────────────────────────────────────
    backend = detect_backend(settings.inference_backend)
    info    = get_backend_info(backend)
    quant   = gpu_manager.quantization

    # ── 2. Start GPU batch worker ───────────────────────────────────────────
    client = InferenceClient(backend_override=settings.inference_backend)

    async def _inference_fn(messages, temperature=0.3, max_tokens=4096):
        return await client.generate(messages, temperature, max_tokens)

    await gpu_manager.start(_inference_fn)

    # ── 3. Startup banner ───────────────────────────────────────────────────
    vram   = gpu_manager.vram_snapshot
    banner = [
        "=" * 64,
        "  AMD AgentForge  v0.1.0 — ONLINE",
        "=" * 64,
        f"  Inference  : {info.get('name', backend.value)}",
        f"  Features   : {', '.join(info.get('features', [])[:3])}",
        f"  Quantize   : {quant['format'].upper()} ({quant['dtype']})",
    ]
    if vram:
        banner += [
            f"  VRAM Free  : {vram.free_gb} GB / {vram.total_mb // 1024} GB",
            f"  GPU Util   : {vram.utilization}%",
        ]
    banner += [
        f"  Sandbox    : {'Enabled  (Docker)' if settings.sandbox_enabled else 'Disabled'}",
        f"  CORS       : {settings.cors_origins}",
        f"  Batch max  : {gpu_manager.batch_queue.max_batch_size} requests",
        "=" * 64,
    ]
    for line in banner:
        logger.info(line)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("AgentForge shutting down…")
    await gpu_manager.stop()
    logger.info("Clean shutdown complete")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "AMD AgentForge",
    description = (
        "Autonomous multi-agent system that converts natural language "
        "into deployable full-stack applications.  Optimized for AMD ROCm "
        "GPU acceleration with vLLM + PagedAttention inference."
    ),
    version   = "0.1.0",
    lifespan  = lifespan,
    docs_url  = "/docs",
    redoc_url = "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.cors_origin_list,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── WebSocket (Module 1) ──────────────────────────────────────────────────────
# Registered directly (not via APIRouter) so FastAPI sees it as a websocket route.
app.add_api_websocket_route("/ws/generate", websocket_endpoint)

# ── REST Routes ───────────────────────────────────────────────────────────────
app.include_router(generate_router, tags=["Generate"])     # HTTP fallback + REST
app.include_router(status_router,   prefix="/api", tags=["Status"])
app.include_router(deploy_router,   prefix="/api", tags=["Deploy"])


# ── Health & GPU Endpoints ────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    return {
        "service":  "AMD AgentForge",
        "version":  "0.1.0",
        "docs":     "/docs",
        "status":   "operational",
        "ws":       "ws://[host]:8080/ws/generate",
    }


@app.get("/api/gpu", tags=["Status"])
async def gpu_status():
    """
    Real-time GPU telemetry endpoint.
    Returns VRAM usage, utilization, and batch queue stats.
    On AMD ROCm systems, values come directly from rocm-smi.
    On API-mode systems, values are synthetic for UI display.
    """
    gpu_manager.refresh_vram()
    return {
        "backend":     detect_backend(settings.inference_backend).value,
        **gpu_manager.telemetry,
        "quantization_rationale": gpu_manager.quantization.get("rationale"),
        "vllm_args":              gpu_manager.quantization.get("vllm_args", []),
    }


@app.get("/api/gpu/log", tags=["Status"])
async def gpu_log():
    """
    Returns the last GPU kernel activity log in the format shown by
    the 'Live Kernel Log' dashboard component.  On real hardware this
    would tail /sys/kernel/debug/amdgpu/*.  In demo mode it returns
    a structured synthetic log.
    """
    import random, time as _time
    kernels = [
        "flash_attn_fwd_rocm",    "paged_attention_v2_hip",
        "gemm_bf16_mi300x",       "rotary_embedding_rocm",
        "rms_norm_fwd_hip",       "sampling_from_probs",
        "copy_blocks_kernel",     "gather_blocks_kernel",
        "reshape_and_cache_hip",  "advance_step_flashattn",
    ]
    entries = []
    base_ts = _time.time() - 10
    for i in range(12):
        entries.append({
            "timestamp":    round(base_ts + i * 0.85, 3),
            "kernel":       random.choice(kernels),
            "grid":         f"({random.choice([1,2,4,8,16])}, 1, 1)",
            "block":        "(256, 1, 1)",
            "duration_us":  random.randint(120, 4500),
            "vram_delta_mb": random.randint(-512, 512),
        })
    return {"log": entries, "source": "synthetic (no /sys/kernel/debug on this host)"}


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host      = settings.app_host,
        port      = settings.app_port,
        reload    = True,
        log_level = settings.log_level,
        ws        = "websockets",        # Ensure WS support on uvicorn
    )
