"""
Architect Agent — Converts natural language prompts into structured
application blueprints (JSON schema).
"""

import json
import logging
from pathlib import Path

from backend.core.inference.client import InferenceClient

logger = logging.getLogger(__name__)

# Load system prompt from markdown file
_PROMPT_PATH = Path(__file__).parent / "prompts" / "architect.md"
ARCHITECT_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


async def run_architect(user_prompt: str, client: InferenceClient | None = None) -> dict:
    """
    Generate an application architecture schema from a user prompt.

    Args:
        user_prompt: Natural language description of the desired application.
        client: Optional InferenceClient instance (creates one if not provided).

    Returns:
        Parsed JSON architecture schema dictionary.

    Raises:
        ValueError: If the LLM output cannot be parsed as valid JSON.
    """
    if client is None:
        client = InferenceClient()

    logger.info(f"Architect processing prompt: {user_prompt[:100]}...")

    messages = [
        {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    schema = await client.generate_json(
        messages=messages,
        temperature=0.3,
        max_tokens=4096,
    )

    # Validate required fields
    required_keys = ["app_name", "app_type", "tech_stack", "file_tree"]
    missing = [k for k in required_keys if k not in schema]
    if missing:
        raise ValueError(f"Architecture schema missing required keys: {missing}")

    logger.info(
        f"Architecture generated: {schema['app_name']} "
        f"({schema['app_type']}, {len(schema.get('file_tree', []))} files)"
    )

    return schema
