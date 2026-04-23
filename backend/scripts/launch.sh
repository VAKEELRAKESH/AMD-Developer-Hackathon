#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Launch Script — Starts vLLM inference server + FastAPI backend
# Used inside the ROCm Docker container
# ──────────────────────────────────────────────────────────────

set -e

MODEL="${VLLM_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
VLLM_PORT=8000
API_PORT=8080

echo "═══════════════════════════════════════════════════════"
echo "  AMD AgentForge — Launch Sequence"
echo "  Model: ${MODEL}"
echo "  vLLM Port: ${VLLM_PORT}"
echo "  API Port:  ${API_PORT}"
echo "═══════════════════════════════════════════════════════"

# ── Step 1: Start vLLM inference server in background ────────
echo "[1/2] Starting vLLM inference server..."
python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL}" \
    --dtype float16 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.90 \
    --block-size 16 \
    --swap-space 4 \
    --enforce-eager \
    --tokenizer-pool-size 2 \
    --max-num-batched-tokens 8192 \
    --max-num-seqs 64 \
    --port ${VLLM_PORT} \
    &

VLLM_PID=$!

# Wait for vLLM to be ready
echo "Waiting for vLLM to be ready..."
for i in $(seq 1 60); do
    if curl -s http://localhost:${VLLM_PORT}/health > /dev/null 2>&1; then
        echo "vLLM ready after ${i}s"
        break
    fi
    sleep 1
done

# ── Step 2: Start FastAPI application ────────────────────────
echo "[2/2] Starting FastAPI application..."
export INFERENCE_BACKEND=vllm_rocm
export VLLM_URL="http://localhost:${VLLM_PORT}/v1"

uvicorn main:app \
    --host 0.0.0.0 \
    --port ${API_PORT} \
    --workers 1 \
    &

API_PID=$!

echo "═══════════════════════════════════════════════════════"
echo "  AgentForge is running!"
echo "  API:  http://localhost:${API_PORT}"
echo "  Docs: http://localhost:${API_PORT}/docs"
echo "  vLLM: http://localhost:${VLLM_PORT}"
echo "═══════════════════════════════════════════════════════"

# Wait for either process to exit
wait -n $VLLM_PID $API_PID
