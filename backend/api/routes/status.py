"""
Status Endpoint — REST API for checking system and session status.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import settings
from core.inference.router import detect_backend, get_backend_info

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    inference_backend: dict
    sandbox_enabled: bool


class InferenceInfoResponse(BaseModel):
    backend: str
    name: str
    icon: str
    color: str
    description: str
    features: list[str]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check with inference backend info."""
    backend = detect_backend(settings.inference_backend)
    info = get_backend_info(backend)

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        inference_backend=info,
        sandbox_enabled=settings.sandbox_enabled,
    )


@router.get("/inference", response_model=InferenceInfoResponse)
async def inference_info():
    """Detailed inference backend information for the UI."""
    backend = detect_backend(settings.inference_backend)
    info = get_backend_info(backend)

    return InferenceInfoResponse(
        backend=backend.value,
        **info,
    )
