"""Workflow builder for creating workflows based on document type."""

from typing import Any

from ..llm.adapter import LLMAdapter
from ..utils.logger import get_logger
from .nodes import NODES  # NODES already includes EXTENDED_NODES via **EXTENDED_NODES
from .state_machine import CheckpointManager, StateMachine, WorkflowContext

logger = get_logger(__name__)


# Standard paper workflow node sequence (using extended nodes for full features)
PAPER_WORKFLOW = [
    "paper_feasibility",
    "paper_research",
    "paper_drafting",
    "paper_validation",
    "paper_publishing",
]

# Patent workflow node sequence
PATENT_WORKFLOW = [
    "intent_analysis",
    "patent_feasibility",
    "patent_research",
    "patent_drafting",
    "patent_validation",
    "patent_publishing",
]


def get_workflow_sequence(doc_type: str) -> list[str]:
    """Get the workflow node sequence for a document type."""
    doc_type = doc_type.upper()

    if doc_type == "PATENT":
        return PATENT_WORKFLOW
    elif doc_type in ("PAPER", "ABSTRACT", "SURVEY", "PROPOSAL", "THESIS"):
        return PAPER_WORKFLOW
    else:
        # Default to paper workflow
        logger.warning("unknown_doc_type", doc_type=doc_type, default="PAPER")
        return PAPER_WORKFLOW


def build_workflow(
    doc_type: str,
    llm_adapter: LLMAdapter,
    start_node: str | None = None,
    checkpoint_manager: CheckpointManager | None = None,
) -> StateMachine:
    """Build a workflow state machine for the given document type.

    Args:
        doc_type: Document type (PAPER, PATENT, etc.)
        llm_adapter: LLM adapter for the agents
        start_node: Optional starting node name
        checkpoint_manager: Optional CheckpointManager for resume support

    Returns:
        Configured StateMachine instance
    """
    workflow = StateMachine(checkpoint_manager=checkpoint_manager)
    sequence = get_workflow_sequence(doc_type)

    # Create and add nodes in sequence
    for node_name in sequence:
        if node_name in NODES:
            node_class = NODES[node_name]
            # Instantiate node with LLM adapter
            node = node_class(llm_adapter)
            workflow.add_node(node)
            logger.debug("node_added_to_workflow", node=node_name, doc_type=doc_type)
        else:
            logger.warning("node_not_found", node=node_name)

    # Create edges (linear sequence)
    for i in range(len(sequence) - 1):
        workflow.add_edge(sequence[i], sequence[i + 1])

    # Set start node
    start = start_node or sequence[0]
    if start_node and start_node not in sequence:
        raise ValueError(f"Invalid start_node '{start_node}' not in workflow sequence: {sequence}")
    workflow.set_start(start)

    logger.info("workflow_built", doc_type=doc_type, nodes=len(sequence), start=start)

    return workflow


async def execute_workflow_by_doc_type(
    doc_type: str,
    context: WorkflowContext,
    llm_adapter: LLMAdapter,
    start_at: str | None = None,
    checkpoint_manager: CheckpointManager | None = None,
) -> dict[str, Any]:
    """Execute a workflow based on document type.

    Args:
        doc_type: Document type (PAPER, PATENT, etc.)
        context: Workflow context with task details
        llm_adapter: LLM adapter for the agents
        start_at: Optional starting node name
        checkpoint_manager: Optional CheckpointManager for resume support

    Returns:
        Workflow execution result
    """
    workflow = build_workflow(doc_type, llm_adapter, start_at, checkpoint_manager)

    result = await workflow.execute(context)

    return result


# Workflow configurations
WORKFLOW_CONFIGS: dict[str, dict[str, Any]] = {
    "PAPER": {
        "name": "Paper Writing Workflow",
        "description": "8-step academic paper writing workflow",
        "sequence": PAPER_WORKFLOW,
    },
    "PATENT": {
        "name": "Patent Writing Workflow",
        "description": "6-step patent application workflow",
        "sequence": PATENT_WORKFLOW,
    },
    "ABSTRACT": {
        "name": "Abstract Writing Workflow",
        "description": "Condensed paper workflow for abstracts",
        "sequence": PAPER_WORKFLOW[:4],  # Just up to drafting
    },
    "SURVEY": {
        "name": "Survey Report Workflow",
        "description": "Literature survey workflow",
        "sequence": PAPER_WORKFLOW,
    },
    "PROPOSAL": {
        "name": "Proposal Writing Workflow",
        "description": "Research proposal workflow",
        "sequence": PAPER_WORKFLOW,
    },
    "THESIS": {
        "name": "Thesis Writing Workflow",
        "description": "Extended thesis writing workflow",
        "sequence": PAPER_WORKFLOW,
    },
}


def get_workflow_config(doc_type: str) -> dict[str, Any]:
    """Get workflow configuration for a document type."""
    return WORKFLOW_CONFIGS.get(doc_type.upper(), WORKFLOW_CONFIGS["PAPER"])


def list_supported_workflows() -> list[dict[str, Any]]:
    """List all supported workflow configurations."""
    return [
        {
            "doc_type": doc_type,
            "name": config["name"],
            "description": config["description"],
            "node_count": len(config["sequence"]),
        }
        for doc_type, config in WORKFLOW_CONFIGS.items()
    ]
