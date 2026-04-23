"""
ForgeState — The single source of truth for the entire pipeline.

This TypedDict is managed by LangGraph's StateGraph and tracks every
aspect of the application generation lifecycle from prompt to deployment.
"""

from typing import TypedDict, Literal, Annotated
from langgraph.graph import add_messages


class ForgeState(TypedDict):
    """
    Central state object for the AgentForge pipeline.

    All agents read from and write to this state. LangGraph manages
    state transitions and ensures consistency across the DAG.
    """

    # ── Identity ──────────────────────────────────────────────
    session_id: str
    user_prompt: str

    # ── Progress Tracking ─────────────────────────────────────
    phase: Literal[
        "intake",           # Prompt received, pipeline starting
        "architecting",     # Architect agent designing schema
        "engineering",      # Engineer agent generating code
        "reviewing",        # Reviewer agent analyzing output
        "sandbox_testing",  # Code executing in sandbox
        "debugging",        # Self-correction loop active
        "deploy_ready",     # All checks passed, ready to ship
        "deployed",         # Successfully deployed to target
        "failed",           # Max retries exceeded, pipeline aborted
    ]

    # ── Agent Outputs ─────────────────────────────────────────
    architecture_schema: dict | None    # Architect's JSON blueprint
    code_blocks: dict[str, str] | None  # {filename: code_content}
    review_result: dict | None          # {status, patches, reasoning}

    # ── Sandbox Results ───────────────────────────────────────
    sandbox_exit_code: int | None
    sandbox_stdout: str | None
    sandbox_stderr: str | None

    # ── Self-Correction Memory ────────────────────────────────
    iteration_count: int                # Current debug cycle (0-indexed)
    max_iterations: int                 # Hard cap (default: 3)
    failure_memory: list[dict]          # [{error, attempted_fix, outcome}]

    # ── Agent Communication Log ───────────────────────────────
    messages: Annotated[list, add_messages]
