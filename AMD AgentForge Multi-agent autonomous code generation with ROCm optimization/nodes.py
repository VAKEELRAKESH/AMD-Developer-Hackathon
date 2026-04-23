"""
core/graph/nodes.py — LangGraph Node Functions

Each async node function receives the current ForgeState, performs its
work, and returns a *partial* state update dict that LangGraph merges
back into the canonical state.

Node responsibilities:
  architect_node  — NL prompt → structured JSON blueprint
  engineer_node   — blueprint → multi-file code (with sandbox pre-check)
  sandbox_node    — executes code in Docker, captures exit/stdout/stderr
  reviewer_node   — analyzes failures → targeted diff patches
"""

import json
import logging
import time
from pathlib import Path

from core.graph.state import ForgeState
from core.agents.architect import run_architect
from core.agents.engineer import run_engineer
from core.agents.reviewer import run_reviewer, apply_patches
from core.sandbox.executor import SandboxExecutor, detect_entry_point, detect_language
from core.inference.client import InferenceClient

logger = logging.getLogger(__name__)

# ── Shared singleton inference client ─────────────────────────────────────────
_client: InferenceClient | None = None


def _get_client() -> InferenceClient:
    global _client
    if _client is None:
        _client = InferenceClient()
    return _client


# ─────────────────────────────────────────────────────────────────────────────
# ARCHITECT NODE
# ─────────────────────────────────────────────────────────────────────────────

async def architect_node(state: ForgeState) -> dict:
    """
    Node: Architect Agent
    Converts the user prompt into a structured JSON application blueprint.

    Output state keys updated:
        architecture_schema, phase, messages
    """
    logger.info(f"[Architect] Processing: {state['user_prompt'][:80]}…")
    t0 = time.monotonic()

    try:
        schema = await run_architect(
            user_prompt = state["user_prompt"],
            client      = _get_client(),
        )
    except Exception as exc:
        logger.error(f"[Architect] Failed: {exc}")
        return {
            "phase":   "failed",
            "messages": [{"role": "system", "content": f"Architect failed: {exc}"}],
        }

    elapsed = round(time.monotonic() - t0, 1)
    file_count  = len(schema.get("file_tree", []))
    route_count = len(schema.get("api_routes", []))
    model_count = len(schema.get("data_models", []))

    logger.info(
        f"[Architect] Done in {elapsed}s — "
        f"{schema.get('app_name')} ({file_count} files, "
        f"{route_count} routes, {model_count} models)"
    )

    return {
        "architecture_schema": schema,
        "phase":               "engineering",
        "messages": [{
            "role":    "assistant",
            "content": (
                f"**Blueprint ready** — {schema.get('app_name', 'App')} "
                f"({schema.get('app_type', 'unknown')})\n"
                f"  • {file_count} files to generate\n"
                f"  • {route_count} API routes\n"
                f"  • {model_count} data models\n"
                f"  • Tech stack: {json.dumps(schema.get('tech_stack', {}))}\n"
                f"  _(designed in {elapsed}s)_"
            ),
        }],
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENGINEER NODE  (Module 3 — Multi-file generation loop)
# ─────────────────────────────────────────────────────────────────────────────

async def engineer_node(state: ForgeState) -> dict:
    """
    Node: Engineer Agent
    Generates all source files defined in the architecture schema.

    Generation strategy:
    1. Sort the file_tree by dependency order (config → models → routes → UI).
    2. Generate each file sequentially, passing previously generated files
       as context (allows cross-file imports to stay consistent).
    3. After generation, run a lightweight pre-flight syntax check
       (ast.parse for Python, JSON.parse for JSON files) before handing
       off to the full Docker sandbox.
    4. If the reviewer already applied patches, skip full regeneration
       and go straight to sandbox re-test.

    On re-entry (iteration_count > 0):
    - If patches exist in review_result, use the patched code from state
      (already applied by reviewer_node) and skip straight to sandbox.
    - If no patches, trigger a full regeneration with the failure context
      visible in the prompt.
    """
    schema    = state["architecture_schema"]
    existing  = state.get("code_blocks")
    iteration = state.get("iteration_count", 0)
    review    = state.get("review_result") or {}

    # ── Re-entry: patches already applied by reviewer_node ───────────────────
    if iteration > 0 and existing and review.get("patches"):
        logger.info(
            f"[Engineer] Iteration {iteration}: "
            f"re-using patched code ({len(existing)} files), skipping generation"
        )
        return {
            "phase": "sandbox_testing",
            "messages": [{
                "role":    "assistant",
                "content": (
                    f"⚙️  Code patched (iteration {iteration}).  "
                    f"Re-submitting {len(existing)} files to sandbox for verification."
                ),
            }],
        }

    # ── Full generation run ───────────────────────────────────────────────────
    file_tree = schema.get("file_tree", [])
    logger.info(
        f"[Engineer] Generating {len(file_tree)} files "
        f"(iteration={iteration})"
    )
    t0 = time.monotonic()

    try:
        code_blocks = await run_engineer(
            architecture_schema = schema,
            existing_code       = existing,
            client              = _get_client(),
        )
    except Exception as exc:
        logger.error(f"[Engineer] Code generation failed: {exc}")
        return {
            "phase":   "failed",
            "messages": [{
                "role":    "system",
                "content": f"Engineer agent failed: {exc}",
            }],
        }

    elapsed       = round(time.monotonic() - t0, 1)
    total_chars   = sum(len(v) for v in code_blocks.values())
    total_lines   = sum(v.count("\n") for v in code_blocks.values())

    # ── Pre-flight syntax check (fast — before spinning up Docker) ────────────
    syntax_errors = _preflight_syntax_check(code_blocks)
    if syntax_errors:
        logger.warning(
            f"[Engineer] Pre-flight syntax errors in "
            f"{list(syntax_errors.keys())} — passing to sandbox anyway"
        )
        # Don't abort — sandbox will catch and explain the error properly

    logger.info(
        f"[Engineer] Generated {len(code_blocks)} files "
        f"({total_lines} lines / {total_chars} chars) in {elapsed}s"
    )

    file_summary = "\n".join(
        f"  • `{fname}` ({code.count(chr(10))} lines)"
        for fname, code in code_blocks.items()
    )

    return {
        "code_blocks": code_blocks,
        "phase":       "sandbox_testing",
        "messages": [{
            "role":    "assistant",
            "content": (
                f"**Code generation complete** ({elapsed}s)\n"
                f"{file_summary}\n"
                f"  _Total: {total_lines} lines, {total_chars} chars_\n"
                + (
                    f"\n⚠️  Pre-flight found syntax hints in: "
                    f"{', '.join(syntax_errors.keys())}"
                    if syntax_errors else
                    "\n✅ Pre-flight syntax check passed — submitting to Docker sandbox…"
                )
            ),
        }],
    }


def _preflight_syntax_check(code_blocks: dict[str, str]) -> dict[str, str]:
    """
    Quick syntax check before spending Docker startup time.
    Returns {filename: error_message} for any problematic files.
    Only checks Python (ast.parse) and JSON (json.loads) files.
    """
    errors: dict[str, str] = {}

    for filename, code in code_blocks.items():
        ext = Path(filename).suffix.lower()

        if ext == ".py":
            try:
                __import__("ast").parse(code)
            except SyntaxError as e:
                errors[filename] = f"SyntaxError line {e.lineno}: {e.msg}"

        elif ext == ".json":
            try:
                json.loads(code)
            except json.JSONDecodeError as e:
                errors[filename] = f"JSONDecodeError: {e.msg} (line {e.lineno})"

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# SANDBOX NODE
# ─────────────────────────────────────────────────────────────────────────────

async def sandbox_node(state: ForgeState) -> dict:
    """
    Node: Sandbox Execution
    Runs generated code inside an ephemeral Docker container.
    Captures exit_code, stdout, and stderr for the Reviewer.

    The "Digital Twin" metaphor:
    Just as you wouldn't commission a physical manufacturing process without
    a simulation run, AgentForge never ships code without executing it in
    an isolated environment first.  The sandbox is the Digital Twin.
    """
    schema      = state["architecture_schema"]
    code_blocks = state["code_blocks"]
    iteration   = state.get("iteration_count", 0)

    entry_point = detect_entry_point(schema)
    language    = detect_language(schema)

    logger.info(
        f"[Sandbox] Executing iteration={iteration}  "
        f"entry={entry_point}  lang={language}  files={len(code_blocks)}"
    )

    executor = SandboxExecutor()
    t0       = time.monotonic()

    try:
        result = await executor.execute(
            code_blocks = code_blocks,
            entry_point = entry_point,
            language    = language,
        )
    except Exception as exc:
        logger.error(f"[Sandbox] Executor raised: {exc}")
        result = {
            "exit_code": -1,
            "stdout":    "",
            "stderr":    str(exc),
            "timed_out": False,
        }

    elapsed    = round(time.monotonic() - t0, 1)
    exit_code  = result["exit_code"]
    timed_out  = result.get("timed_out", False)
    phase      = "deploy_ready" if exit_code == 0 else "reviewing"

    update: dict = {
        "sandbox_exit_code": exit_code,
        "sandbox_stdout":    result.get("stdout", ""),
        "sandbox_stderr":    result.get("stderr", ""),
        "phase":             phase,
    }

    if exit_code == 0:
        update["messages"] = [{
            "role":    "assistant",
            "content": (
                f"✅ **Sandbox PASSED** (exit 0, {elapsed}s)\n"
                f"stdout preview: {result.get('stdout', '')[:500]}"
            ),
        }]
        logger.info(f"[Sandbox] PASSED  elapsed={elapsed}s")

    else:
        new_iter = iteration + 1
        update["iteration_count"] = new_iter

        stderr_preview = (result.get("stderr") or "")[:600]
        timeout_note   = "  ⏱️  Container timed out.\n" if timed_out else ""

        update["messages"] = [{
            "role":    "system",
            "content": (
                f"❌ **Sandbox FAILED** (exit {exit_code}, {elapsed}s)\n"
                f"{timeout_note}"
                f"stderr:\n```\n{stderr_preview}\n```\n"
                f"Iteration: {new_iter}/{state.get('max_iterations', 3)}"
            ),
        }]
        logger.warning(
            f"[Sandbox] FAILED  exit={exit_code}  iter={new_iter}  "
            f"elapsed={elapsed}s"
        )

    return update


# ─────────────────────────────────────────────────────────────────────────────
# REVIEWER NODE
# ─────────────────────────────────────────────────────────────────────────────

async def reviewer_node(state: ForgeState) -> dict:
    """
    Node: Reviewer / Sentry Agent (The Shadow Debugger)
    Analyzes sandbox failures, generates targeted diff patches, and
    records each attempt in failure_memory to prevent circular fixes.

    The Sentry reads:
      • The current code_blocks
      • The exact stderr/stdout from the sandbox
      • The previous failure_memory (to avoid repeating broken fixes)
    It outputs:
      • A diagnosis (root cause as a sentence)
      • A confidence score (0.0–1.0)
      • A list of {file, search, replace} patches
    """
    iteration = state.get("iteration_count", 0)
    stderr    = state.get("sandbox_stderr", "") or ""
    logger.info(f"[Reviewer] Analyzing failure  iteration={iteration}")

    try:
        review_result = await run_reviewer(
            architecture_schema = state["architecture_schema"],
            code_blocks         = state["code_blocks"],
            exit_code           = state.get("sandbox_exit_code", -1),
            stderr              = stderr,
            stdout              = state.get("sandbox_stdout", "") or "",
            failure_memory      = state.get("failure_memory", []),
            iteration           = iteration,
            client              = _get_client(),
        )
    except Exception as exc:
        logger.error(f"[Reviewer] Analysis failed: {exc}")
        return {
            "phase":   "failed",
            "messages": [{
                "role":    "system",
                "content": f"Reviewer agent failed: {exc}",
            }],
        }

    # Apply patches to the current code
    patches      = review_result.get("patches", [])
    patched_code = apply_patches(state["code_blocks"], patches)

    # Append to failure memory (outcome = "pending" until next sandbox run)
    new_memory = {
        "error":         stderr[:500],
        "diagnosis":     review_result.get("diagnosis", "")[:500],
        "attempted_fix": json.dumps(patches)[:600],
        "outcome":       "pending",
    }

    # Mark previous memory entry outcome as "fixed" or "failed" based on
    # whether this round's patches differ from the last
    memory = list(state.get("failure_memory", []))
    if memory:
        memory[-1] = {**memory[-1], "outcome": "not_fixed"}
    memory.append(new_memory)

    confidence = review_result.get("confidence", 0.0)
    diagnosis  = review_result.get("diagnosis", "N/A")

    logger.info(
        f"[Reviewer] Diagnosis='{diagnosis}'  "
        f"patches={len(patches)}  confidence={confidence:.0%}"
    )

    return {
        "code_blocks":    patched_code,
        "review_result":  review_result,
        "failure_memory": memory,
        "phase":          "engineering",
        "messages": [{
            "role":    "assistant",
            "content": (
                f"🔧 **Shadow Debugger Report** (iteration {iteration})\n"
                f"  Diagnosis:  {diagnosis}\n"
                f"  Confidence: {confidence:.0%}\n"
                f"  Patches:    {len(patches)} applied\n"
                + (
                    "\n".join(
                        f"  • `{p.get('file', '?')}` — "
                        + (p.get('search', '')[:60] or '(new content)')
                        for p in patches[:5]
                    )
                )
                + f"\n  Re-routing to Engineer for validation…"
            ),
        }],
    }
