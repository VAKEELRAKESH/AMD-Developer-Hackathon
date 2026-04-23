"""
Engineer Agent — Generates complete code files from architecture schemas.

Processes files in dependency order, maintaining context of previously
generated files for import consistency.
"""

import json
import logging
from pathlib import Path

from core.inference.client import InferenceClient

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "engineer.md"
ENGINEER_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


async def run_engineer(
    architecture_schema: dict,
    existing_code: dict[str, str] | None = None,
    client: InferenceClient | None = None,
) -> dict[str, str]:
    """
    Generate code for all files defined in the architecture schema.

    Args:
        architecture_schema: The Architect's JSON blueprint.
        existing_code: Previously generated code (for re-generation after patches).
        client: Optional InferenceClient instance.

    Returns:
        Dictionary mapping filename → generated code content.
    """
    if client is None:
        client = InferenceClient()

    file_tree = architecture_schema.get("file_tree", [])
    if not file_tree:
        raise ValueError("Architecture schema has no file_tree defined")

    # Sort files by dependency order (models/config first, then routes, then UI)
    sorted_files = _sort_by_dependency(file_tree)
    logger.info(f"Generating {len(sorted_files)} files in dependency order")

    code_blocks: dict[str, str] = {}

    for i, filepath in enumerate(sorted_files):
        logger.info(f"[{i+1}/{len(sorted_files)}] Generating: {filepath}")

        # Build context with previously generated files
        context_parts = [
            f"## Architecture Schema\n```json\n{json.dumps(architecture_schema, indent=2)}\n```",
        ]

        if code_blocks:
            prev_files = "\n\n".join([
                f"### {fname}\n```\n{code}\n```"
                for fname, code in code_blocks.items()
            ])
            context_parts.append(f"## Previously Generated Files\n{prev_files}")

        # If we have existing code for this file (re-generation), include it
        if existing_code and filepath in existing_code:
            context_parts.append(
                f"## Previous Version (being regenerated)\n"
                f"```\n{existing_code[filepath]}\n```"
            )

        context = "\n\n".join(context_parts)

        messages = [
            {"role": "system", "content": ENGINEER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Generate the complete code for the file: `{filepath}`\n\n"
                    f"{context}"
                ),
            },
        ]

        code = await client.generate(
            messages=messages,
            temperature=0.2,
            max_tokens=8192,
        )

        # Clean up any markdown fences the LLM might add
        code = _clean_code_output(code, filepath)
        code_blocks[filepath] = code

    logger.info(f"All {len(code_blocks)} files generated successfully")
    return code_blocks


def _sort_by_dependency(file_tree: list[str]) -> list[str]:
    """
    Sort files so that dependencies are generated before their dependents.

    Priority (generated first → last):
    1. Config files (.env, config.py, settings.py)
    2. Database models (models.py, schema.prisma)
    3. Utilities and helpers
    4. Backend routes/handlers
    5. Frontend components
    6. Entry points (main.py, app.py, page.tsx)
    7. Package manifests (requirements.txt, package.json)
    """
    priority_map = {
        "config": 0,
        "settings": 0,
        ".env": 0,
        "models": 1,
        "schema": 1,
        "database": 1,
        "db": 1,
        "utils": 2,
        "helpers": 2,
        "lib": 2,
        "middleware": 3,
        "routes": 4,
        "handlers": 4,
        "api": 4,
        "components": 5,
        "layout": 6,
        "page": 7,
        "main": 7,
        "app": 7,
        "index": 7,
        "requirements": 8,
        "package.json": 8,
    }

    def get_priority(filepath: str) -> int:
        name = Path(filepath).stem.lower()
        for key, priority in priority_map.items():
            if key in name or key in filepath.lower():
                return priority
        return 5  # Default: middle priority

    return sorted(file_tree, key=get_priority)


def _clean_code_output(code: str, filepath: str) -> str:
    """Remove markdown fences and other artifacts from LLM code output."""
    code = code.strip()

    # Remove opening fence
    if code.startswith("```"):
        first_newline = code.find("\n")
        if first_newline != -1:
            code = code[first_newline + 1:]

    # Remove closing fence
    if code.rstrip().endswith("```"):
        code = code.rstrip()[:-3].rstrip()

    return code
