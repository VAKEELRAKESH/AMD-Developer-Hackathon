"""
Unified Inference Client.

Provides a single async interface for LLM generation regardless of the
underlying backend (vLLM/ROCm, vLLM/CUDA, llama.cpp, or HuggingFace API).
"""

import os
import json
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from .router import detect_backend, InferenceBackend
from core.config import settings

logger = logging.getLogger(__name__)


class InferenceClient:
    """
    Unified async LLM client that adapts to the detected hardware backend.

    Uses the OpenAI-compatible API protocol, which is supported by:
    - vLLM's built-in API server
    - llama.cpp's server mode
    - HuggingFace Inference API (OpenAI-compatible endpoint)
    """

    def __init__(self, backend_override: str | None = None):
        override = backend_override or settings.inference_backend
        self.backend = detect_backend(override)
        self._client = self._init_client()
        self._model = self._get_model_name()
        logger.info(f"InferenceClient initialized: backend={self.backend.value}, model={self._model}")

    def _init_client(self) -> AsyncOpenAI:
        """Initialize the OpenAI-compatible async client for the detected backend."""
        match self.backend:
            case InferenceBackend.VLLM_ROCM | InferenceBackend.VLLM_CUDA:
                return AsyncOpenAI(
                    base_url=settings.vllm_url,
                    api_key="not-needed",
                )
            case InferenceBackend.LLAMA_CPP:
                return AsyncOpenAI(
                    base_url="http://localhost:8080/v1",
                    api_key="not-needed",
                )
            case InferenceBackend.HF_API:
                if not settings.hf_token or settings.hf_token.startswith("hf_xxx"):
                    logger.warning(
                        "HF_TOKEN is missing or still a placeholder — "
                        "set a real token in backend/.env  "
                        "(get one at https://huggingface.co/settings/tokens)"
                    )
                return AsyncOpenAI(
                    base_url="https://router.huggingface.co/v1",
                    api_key=settings.hf_token,
                )

    def _get_model_name(self) -> str:
        """Return the appropriate model identifier for the backend."""
        match self.backend:
            case InferenceBackend.VLLM_ROCM | InferenceBackend.VLLM_CUDA:
                return settings.vllm_model
            case InferenceBackend.LLAMA_CPP:
                return "llama-3.1-8b-instruct"
            case InferenceBackend.HF_API:
                return "mistralai/Mistral-7B-Instruct-v0.3"

    async def generate(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> str:
        """
        Generate a completion from the LLM.

        Args:
            messages: Chat messages in OpenAI format [{role, content}, ...]
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            response_format: Optional structured output format (e.g., {"type": "json_object"})

        Returns:
            The generated text content.
        """
        params = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            params["response_format"] = response_format

        try:
            response = await self._client.chat.completions.create(**params)
            content = response.choices[0].message.content
            logger.debug(
                f"Generated {len(content)} chars "
                f"(tokens: {response.usage.completion_tokens if response.usage else 'N/A'})"
            )
            return content
        except Exception as e:
            logger.error(f"Inference error on {self.backend.value}: {e}")
            raise

    async def generate_stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """
        Stream a completion from the LLM, yielding chunks as they arrive.

        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated.
        """
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def generate_json(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Generate a JSON response from the LLM.

        Falls back to manual JSON extraction if the backend doesn't
        support native JSON mode.

        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON dictionary.
        """
        # Try native JSON mode first
        try:
            content = await self.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(content)
        except Exception:
            # Fallback: generate plain text and extract JSON
            content = await self.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return self._extract_json(content)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from LLM output that may contain markdown fences."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ``` blocks
        import re
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding first { ... } block
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract valid JSON from LLM response: {text[:200]}...")
