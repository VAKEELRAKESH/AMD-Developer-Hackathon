"""
Reviewer / Debugger Agent — Analyzes sandbox failures and produces
targeted diff patches. Maintains failure memory to avoid repeating
the same broken fixes.
"""

import json
import logging
from pathlib import Path

from core.inference.client import InferenceClient

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "reviewer.md"
REVIEWER_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


async def run_reviewer(
    architecture_schema: dict,
    code_blocks: dict[str, str],
    exit_code: int,
    stderr: str,
    stdout: str,
    failure_memory: list[dict],
    iteration: int = 0,
    client: InferenceClient | None = None,
) -> dict:
    """
    Analyze a sandbox failure and produce targeted patches.

    Args:
        architecture_schema: The original architecture JSON.
        code_blocks: Current code for all files.
        exit_code: Sandbox exit code (non-zero = failure).
        stderr: Captured stderr from the sandbox.
        stdout: Captured stdout from the sandbox.
        failure_memory: List of previous debug attempts.
        iteration: Current debug iteration (affects temperature).
        client: Optional InferenceClient instance.

    Returns:
        Review result dict with diagnosis, patches, and confidence score.
    """
    if client is None:
        client = InferenceClient()

    # Format failure memory for the prompt
    memory_str = _format_failure_memory(failure_memory)

    # Format current code blocks
    code_str = "\n\n".join([
        f"### {fname}\n```\n{code}\n```"
        for fname, code in code_blocks.items()
    ])

    # Build the analysis prompt
    analysis_prompt = (
        f"## Previous Failures (DO NOT REPEAT THESE FIXES):\n{memory_str}\n\n"
        f"## Architecture Schema:\n```json\n{json.dumps(architecture_schema, indent=2)}\n```\n\n"
        f"## Current Code:\n{code_str}\n\n"
        f"## Sandbox Error:\n"
        f"Exit code: {exit_code}\n"
        f"stderr:\n```\n{stderr[:3000]}\n```\n"
        f"stdout:\n```\n{stdout[:1000]}\n```"
    )

    messages = [
        {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
        {"role": "user", "content": analysis_prompt},
    ]

    # Decrease temperature with each iteration for more deterministic fixes
    temperature = max(0.02, 0.1 - (iteration * 0.04))

    review_result = await client.generate_json(
        messages=messages,
        temperature=temperature,
        max_tokens=4096,
    )

    logger.info(
        f"Review complete: diagnosis='{review_result.get('diagnosis', 'N/A')}', "
        f"patches={len(review_result.get('patches', []))}, "
        f"confidence={review_result.get('confidence', 0)}"
    )

    return review_result


def apply_patches(
    code_blocks: dict[str, str],
    patches: list[dict],
) -> dict[str, str]:
    """
    Apply diff patches to code blocks.

    Args:
        code_blocks: Current code {filename: content}.
        patches: List of {file, search, replace} patch dicts.

    Returns:
        Updated code blocks with patches applied.
    """
    patched = dict(code_blocks)  # Shallow copy

    for i, patch in enumerate(patches):
        filename = patch.get("file", "")
        search = patch.get("search", "")
        replace = patch.get("replace", "")

        if filename not in patched:
            logger.warning(f"Patch {i}: file '{filename}' not found in code blocks, skipping")
            continue

        if search not in patched[filename]:
            logger.warning(
                f"Patch {i}: search string not found in '{filename}', "
                f"attempting fuzzy match..."
            )
            # Try with stripped whitespace
            stripped_search = search.strip()
            if stripped_search and stripped_search in patched[filename]:
                patched[filename] = patched[filename].replace(stripped_search, replace.strip(), 1)
                logger.info(f"Patch {i}: fuzzy match succeeded for '{filename}'")
            else:
                logger.error(f"Patch {i}: could not apply to '{filename}'")
            continue

        patched[filename] = patched[filename].replace(search, replace, 1)
        logger.info(f"Patch {i}: applied to '{filename}'")

    return patched


def _format_failure_memory(memory: list[dict]) -> str:
    """Format failure memory for the reviewer prompt."""
    if not memory:
        return "  (none — this is the first debug attempt)"

    lines = []
    for i, entry in enumerate(memory):
        lines.append(
            f"  Attempt {i + 1}:\n"
            f"    Error: {entry.get('error', 'N/A')[:300]}\n"
            f"    Fix tried: {entry.get('attempted_fix', 'N/A')[:300]}\n"
            f"    Outcome: {entry.get('outcome', 'N/A')}"
        )
    return "\n".join(lines)
