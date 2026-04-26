"""
Conditional Edge Functions.

These functions determine which node to transition to based on
the current state. Used with LangGraph's add_conditional_edges().
"""

import logging
from backend.core.graph.state import ForgeState

logger = logging.getLogger(__name__)


def should_retry_or_deploy(state: ForgeState) -> str:
    """
    Decision function for the sandbox → next_node conditional edge.

    Routing logic:
    - exit_code == 0 → "deploy_ready" (pipeline complete)
    - iteration_count >= max_iterations → "failed" (abort)
    - otherwise → "reviewer" (enter debug loop)

    Returns:
        One of: "deploy_ready", "failed", "reviewer"
    """
    exit_code = state.get("sandbox_exit_code", -1)
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 3)

    if exit_code == 0:
        logger.info("[Edge] Sandbox passed → deploy_ready")
        return "deploy_ready"

    if iteration >= max_iter:
        logger.warning(
            f"[Edge] Max iterations ({max_iter}) reached → failed. "
            f"Last error: {(state.get('sandbox_stderr') or 'N/A')[:200]}"
        )
        return "failed"

    logger.info(f"[Edge] Sandbox failed (iter {iteration}/{max_iter}) → reviewer")
    return "reviewer"
