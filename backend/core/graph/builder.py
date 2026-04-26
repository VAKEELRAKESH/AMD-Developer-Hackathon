"""
LangGraph DAG Builder.

Assembles the ForgeGraph — a directed acyclic graph with a bounded
retry loop for self-correction.

Graph topology:
    START → architect → engineer → sandbox → [conditional]
                                                ├─ deploy_ready → END
                                                ├─ failed → END
                                                └─ reviewer → engineer (bounded loop)
"""

import logging
from langgraph.graph import StateGraph, START, END

from backend.core.graph.state import ForgeState
from backend.core.graph.nodes import (
    architect_node,
    engineer_node,
    sandbox_node,
    reviewer_node,
)
from backend.core.graph.edges import should_retry_or_deploy

logger = logging.getLogger(__name__)


def build_forge_graph():
    """
    Construct and compile the AgentForge pipeline graph.

    Returns:
        A compiled LangGraph StateGraph ready for .ainvoke() or .astream().
    """
    logger.info("Building ForgeGraph DAG...")

    graph = StateGraph(ForgeState)

    # ── Register Nodes ────────────────────────────────────────
    graph.add_node("architect", architect_node)
    graph.add_node("engineer", engineer_node)
    graph.add_node("sandbox", sandbox_node)
    graph.add_node("reviewer", reviewer_node)

    # ── Define Edges ──────────────────────────────────────────

    # Linear flow: START → architect → engineer → sandbox
    graph.add_edge(START, "architect")
    graph.add_edge("architect", "engineer")
    graph.add_edge("engineer", "sandbox")

    # Conditional branching after sandbox execution
    graph.add_conditional_edges(
        "sandbox",
        should_retry_or_deploy,
        {
            "reviewer": "reviewer",
            "deploy_ready": END,
            "failed": END,
        },
    )

    # Reviewer always loops back to engineer (bounded by edge condition)
    graph.add_edge("reviewer", "engineer")

    compiled = graph.compile()
    logger.info("ForgeGraph compiled successfully")

    return compiled
