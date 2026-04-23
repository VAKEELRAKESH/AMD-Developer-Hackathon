"""
GPU-Aware Inference Router.

Detects available hardware (AMD ROCm → NVIDIA CUDA → CPU → API)
and selects the optimal inference backend at startup.
"""

import subprocess
import os
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class InferenceBackend(Enum):
    """Supported inference backends, ordered by performance priority."""

    VLLM_ROCM = "vllm_rocm"    # AMD GPU with ROCm drivers
    VLLM_CUDA = "vllm_cuda"    # NVIDIA GPU with CUDA
    LLAMA_CPP = "llama_cpp"    # CPU fallback via llama.cpp (quantized)
    HF_API = "hf_api"          # HuggingFace Inference API (remote)


def detect_backend(override: str = "auto") -> InferenceBackend:
    """
    Detect the optimal inference backend based on available hardware.

    Priority order:
      1. ROCm GPU (AMD) → vLLM with HIP kernels
      2. CUDA GPU (NVIDIA) → vLLM with CUDA kernels
      3. llama.cpp binary → CPU inference with GGUF models
      4. HuggingFace API → Remote, rate-limited fallback

    Args:
        override: Force a specific backend. "auto" enables detection.

    Returns:
        The selected InferenceBackend enum value.
    """
    # Allow manual override via config
    if override != "auto":
        try:
            backend = InferenceBackend(override)
            logger.info(f"Backend override: {backend.value}")
            return backend
        except ValueError:
            logger.warning(f"Invalid backend override '{override}', falling back to auto-detection")

    # 1. Check for AMD ROCm
    if _check_rocm():
        logger.info("Detected AMD ROCm GPU → using VLLM_ROCM backend")
        return InferenceBackend.VLLM_ROCM

    # 2. Check for NVIDIA CUDA
    if _check_cuda():
        logger.info("Detected NVIDIA CUDA GPU → using VLLM_CUDA backend")
        return InferenceBackend.VLLM_CUDA

    # 3. Check for llama.cpp
    if _check_llama_cpp():
        logger.info("Detected llama.cpp installation → using LLAMA_CPP backend")
        return InferenceBackend.LLAMA_CPP

    # 4. Fallback to HuggingFace API
    logger.info("No local GPU/CPU inference detected → using HF_API backend")
    return InferenceBackend.HF_API


def _check_rocm() -> bool:
    """Check if AMD ROCm compute devices are present."""
    if os.path.exists("/dev/kfd") and os.path.exists("/dev/dri"):
        logger.debug("Detected AMD Compute nodes (/dev/kfd, /dev/dri)")
        return True
    
    # Fallback to rocm-smi check
    try:
        result = subprocess.run(
            ["rocm-smi", "--showid"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "GPU" in result.stdout:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def _check_cuda() -> bool:
    """Check if NVIDIA CUDA drivers and a compatible GPU are present."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.debug(f"CUDA GPU: {result.stdout.strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def _check_llama_cpp() -> bool:
    """Check if llama.cpp server binary is available."""
    search_paths = [
        "/usr/local/bin/llama-server",
        "/usr/bin/llama-server",
        os.path.expanduser("~/.local/bin/llama-server"),
        "./llama.cpp/build/bin/llama-server",
    ]
    for path in search_paths:
        if os.path.exists(path):
            logger.debug(f"Found llama.cpp at: {path}")
            return True
    return False


def get_backend_info(backend: InferenceBackend) -> dict:
    """Return metadata about the selected backend for UI display."""
    info_map = {
        InferenceBackend.VLLM_ROCM: {
            "name": "vLLM (AMD ROCm)",
            "icon": "gpu",
            "color": "red",
            "description": "Local inference via vLLM with AMD ROCm/HIP acceleration",
            "features": ["PagedAttention", "FlashAttention-2 HIP", "Continuous Batching"],
        },
        InferenceBackend.VLLM_CUDA: {
            "name": "vLLM (NVIDIA CUDA)",
            "icon": "gpu",
            "color": "green",
            "description": "Local inference via vLLM with NVIDIA CUDA acceleration",
            "features": ["PagedAttention", "FlashAttention-2", "Continuous Batching"],
        },
        InferenceBackend.LLAMA_CPP: {
            "name": "llama.cpp (CPU)",
            "icon": "cpu",
            "color": "blue",
            "description": "Local CPU inference via quantized GGUF models",
            "features": ["Q4_K_M Quantization", "AVX2/AVX-512"],
        },
        InferenceBackend.HF_API: {
            "name": "HuggingFace API",
            "icon": "cloud",
            "color": "yellow",
            "description": "Remote inference via HuggingFace Inference API (rate-limited)",
            "features": ["No local hardware required", "Rate limited"],
        },
    }
    return info_map.get(backend, {})
