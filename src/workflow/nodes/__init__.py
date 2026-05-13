"""Workflow node implementations."""

from ...llm.adapter import BaseLLMAdapter
from ...utils.logger import get_logger
from ...workflow.state_machine import NodeResult, NodeStatus, WorkflowContext, WorkflowNode
from .extended import EXTENDED_NODES

logger = get_logger(__name__)


class IntentAnalysisNode(WorkflowNode):
    """Node 1: Intent Analysis"""

    name = "intent_analysis"
    timeout_seconds = 30

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("intent_analysis_executing", task_id=context.task_id)

        # Extract domain and doc_type from topic
        # In production, this would call Editor agent
        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "domain": context.domain,
                "doc_type": context.doc_type,
            },
        )


class FeasibilityStudyNode(WorkflowNode):
    """Node 2: Feasibility Study"""

    name = "feasibility_study"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("feasibility_study_executing", task_id=context.task_id)

        # In production, call Investigator agent
        # Simulate pass for now
        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "feasibility": "PASS",
                "innovativeness": {"score": 7, "analysis": "Novel approach"},
                "originality": {"score": 8, "analysis": "Original contribution"},
            },
        )


class DeepResearchNode(WorkflowNode):
    """Node 3: Deep Research"""

    name = "deep_research"
    timeout_seconds = 300

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("deep_research_executing", task_id=context.task_id)

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "literature_review": "# Literature Review\n\nRelevant papers...",
            },
        )


class DraftingNode(WorkflowNode):
    """Node 4: Drafting"""

    name = "drafting"
    timeout_seconds = 180

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("drafting_executing", task_id=context.task_id)

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "draft": "# Research Paper\n\n## Abstract\n...",
                "version": 1,
            },
        )


class LogicValidationNode(WorkflowNode):
    """Node 5: Logic Validation"""

    name = "logic_validation"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("logic_validation_executing", task_id=context.task_id)

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "passed": True,
                "score": 85,
                "issues": [],
            },
        )


class PlagiarismCheckNode(WorkflowNode):
    """Node 6: Plagiarism Check"""

    name = "plagiarism_check"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("plagiarism_check_executing", task_id=context.task_id)

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "passed": True,
                "similarity_rate": 8.5,
            },
        )


class PolishingNode(WorkflowNode):
    """Node 7: Polishing & Humanizing"""

    name = "polishing"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("polishing_executing", task_id=context.task_id)

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "polished_content": "# Polished Research Paper\n\n...",
            },
        )


class PublishingNode(WorkflowNode):
    """Node 8: Publishing"""

    name = "publishing"
    timeout_seconds = 30

    def __init__(self, llm_adapter: BaseLLMAdapter | None = None) -> None:
        self.llm_adapter = llm_adapter

    async def execute(self, context: WorkflowContext) -> NodeResult:
        logger.info("publishing_executing", task_id=context.task_id)

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "output_path": f"workspace/output/{context.task_id}/final.md",
                "status": "published",
            },
        )


# Node registry
NODES = {
    "intent_analysis": IntentAnalysisNode,
    "feasibility_study": FeasibilityStudyNode,
    "deep_research": DeepResearchNode,
    "drafting": DraftingNode,
    "logic_validation": LogicValidationNode,
    "plagiarism_check": PlagiarismCheckNode,
    "polishing": PolishingNode,
    "publishing": PublishingNode,
    **EXTENDED_NODES,  # Include patent and paper nodes
}
