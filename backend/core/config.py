"""
Centralized configuration via Pydantic Settings.
Loads from .env file and environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """Application-wide settings, loaded from environment variables."""

    # --- Inference ---
    hf_token: str = Field(default="", description="HuggingFace API token")
    vllm_model: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct",
        description="Model ID for vLLM server",
    )
    vllm_url: str = Field(
        default="http://localhost:8000/v1",
        description="vLLM OpenAI-compatible API URL",
    )
    inference_backend: Literal["auto", "vllm_rocm", "vllm_cuda", "hf_api", "llama_cpp"] = Field(
        default="auto",
        description="Inference backend selection strategy",
    )

    # --- Application ---
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8080)
    cors_origins: str = Field(default="http://localhost:3000")
    log_level: Literal["debug", "info", "warning", "error"] = Field(default="info")

    # --- Sandbox ---
    sandbox_timeout: int = Field(default=30, description="Sandbox execution timeout in seconds")
    sandbox_memory_limit: str = Field(default="256m", description="Docker memory limit")
    sandbox_enabled: bool = Field(default=True)

    # --- Deployment ---
    vercel_token: str = Field(default="")
    render_api_key: str = Field(default="")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Singleton instance
settings = Settings()
