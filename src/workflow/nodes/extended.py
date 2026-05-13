"""Patent and Paper specific workflow nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ...agents.base import AgentContext
    from ...agents_extended.patent_agent import PatentAgent
    from ...llm.adapter import BaseLLMAdapter
    from ...workflow.state_machine import NodeResult, NodeStatus, WorkflowContext, WorkflowNode

from ...utils.logger import get_logger
from ...utils.workspace import workspace_manager
from ...workflow.state_machine import NodeResult, NodeStatus, WorkflowContext, WorkflowNode

logger = get_logger(__name__)


def _save_to_workspace(task_id: str, subdir: str, filename: str, content: str) -> bool:
    try:
        workspace_path = workspace_manager.get_task_workspace(task_id)
        subdir_path = workspace_path / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)
        file_path = subdir_path / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("saved_to_workspace", task_id=task_id, subdir=subdir, filename=filename, path=str(file_path))
        return True
    except Exception as e:
        logger.error("save_to_workspace_failed", task_id=task_id, subdir=subdir, filename=filename, error=str(e))
        return False


def _format_feasibility_for_display(result: dict[str, Any]) -> str:
    """Format feasibility result as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("FEASIBILITY STUDY REPORT")
    lines.append("=" * 60)
    lines.append(f"\nFeasibility: {result.get('feasibility', 'UNKNOWN')}")
    lines.append(f"Risk of Collision: {result.get('risk_of_collision', 'N/A')}")

    novelty = result.get('novelty_points', [])
    if novelty:
        lines.append("\n--- Novelty Points ---")
        for i, point in enumerate(novelty, 1):
            point_str = point if isinstance(point, str) else ", ".join(str(p) for p in point)
            lines.append(f"{i}. {point_str}")

    related = result.get('related_work', [])
    if related:
        lines.append("\n--- Related Work ---")
        for work in related[:10]:
            work_str = work if isinstance(work, str) else ", ".join(str(w) for w in work)
            lines.append(f"- {work_str}")

    reason = result.get('reason')
    if reason:
        lines.append(f"\nReason: {reason}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def _format_research_for_display(result: dict[str, Any]) -> str:
    """Format research result as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("LITERATURE RESEARCH REPORT")
    lines.append("=" * 60)

    review = result.get('literature_review', '')
    if review:
        lines.append("\n--- Literature Review ---")
        if isinstance(review, list):
            review = "\n".join(str(r) for r in review)
        lines.append(review[:3000] if len(review) > 3000 else review)

    refs = result.get('references', [])
    if refs:
        lines.append(f"\n--- References ({len(refs)} papers) ---")
        for i, ref in enumerate(refs[:20], 1):
            authors = ref.get('authors', [])
            if isinstance(authors, list):
                flat_authors = []
                for a in authors:
                    if isinstance(a, list):
                        flat_authors.extend(a)
                    else:
                        flat_authors.append(a)
                author_str = ", ".join(str(a) for a in flat_authors[:3]) + (" et al." if len(flat_authors) > 3 else "")
            else:
                author_str = str(authors)
            title = ref.get('title', 'Unknown')
            year = ref.get('year', 'N/A')
            doi = ref.get('doi', '')
            lines.append(f"{i}. {author_str} ({year}). {title}. {doi}")

    gaps = result.get('research_gaps', [])
    if gaps:
        lines.append("\n--- Research Gaps ---")
        for gap in gaps:
            gap_str = gap if isinstance(gap, str) else ", ".join(str(g) for g in gap)
            lines.append(f"- {gap_str}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def _format_paper_content_for_display(paper_dict: dict[str, Any]) -> str:
    """Format paper content as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("PAPER DRAFT")
    lines.append("=" * 60)

    lines.append(f"\nTitle: {paper_dict.get('title', 'N/A')}")

    abstract = paper_dict.get('abstract', '')
    if abstract:
        lines.append("\n--- Abstract ---")
        lines.append(abstract)

    keywords = paper_dict.get('keywords', [])
    if keywords:
        lines.append("\n--- Keywords ---")
        lines.append(", ".join(keywords))

    sections = paper_dict.get('sections', {})
    for section_name, section_content in sections.items():
        if section_content:
            lines.append(f"\n--- {section_name.replace('_', ' ').title()} ---")
            if isinstance(section_content, list):
                section_content = "\n".join(str(item) for item in section_content)
            content = section_content[:1000] + "..." if len(section_content) > 1000 else section_content
            lines.append(content)

    refs = paper_dict.get('references', [])
    if refs:
        lines.append(f"\n--- References ({len(refs)} items) ---")
        for i, ref in enumerate(refs[:15], 1):
            authors = ref.get('authors', [])
            if isinstance(authors, list):
                author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            else:
                author_str = str(authors)
            title = ref.get('title', 'Unknown')
            year = ref.get('year', 'N/A')
            lines.append(f"{i}. {author_str} ({year}). {title}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def _format_validation_for_display(result: dict[str, Any]) -> str:
    """Format validation result as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("VALIDATION REPORT")
    lines.append("=" * 60)

    lines.append(f"\nStatus: {result.get('status', 'UNKNOWN')}")

    stats = result.get('statistics', {})
    if stats:
        lines.append("\n--- Statistics ---")
        for key, value in stats.items():
            lines.append(f"{key}: {value}")

    issues = result.get('issues', [])
    if issues:
        lines.append(f"\n--- Issues ({len(issues)} found) ---")
        for issue in issues:
            severity = issue.get('severity', 'unknown')
            desc = issue.get('description', '')
            location = issue.get('location', '')
            lines.append(f"[{severity.upper()}] {location}: {desc}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def _create_agent_context(context: WorkflowContext) -> AgentContext:
    """Convert WorkflowContext to AgentContext for agent methods."""
    from ...agents.base import AgentContext
    return AgentContext(
        task_id=context.task_id,
        topic=context.topic,
        domain=context.domain,
        doc_type=context.doc_type,
        requirements=getattr(context, "requirements", None),
        template_path=getattr(context, "template_path", None),
        template_content=getattr(context, "template_content", None),
        language=context.language,
    )


# Patent-specific nodes


class PatentFeasibilityNode(WorkflowNode):
    """Patent Feasibility Study Node"""

    name = "patent_feasibility"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.patent_agent: PatentAgent | None = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("patent_feasibility_executing", task_id=context.task_id)

        # Lazy init agent
        if self.patent_agent is None:
            from ...agents_extended.patent_agent import PatentAgent
            self.patent_agent = PatentAgent(self.llm_adapter)
            self.patent_agent.patent_skill = self.patent_agent._init_patent_skill()

        skill = cast(Any, self.patent_agent.patent_skill)
        topic = context.topic
        language = context.language

        result = await skill._feasibility_study(topic, language)

        status = NodeStatus.COMPLETED
        if result.get("feasibility") == "FAIL":
            status = NodeStatus.FAILED

        # Save feasibility result to workspace
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "patent_feasibility.json",
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "patent_feasibility_report.txt",
            _format_feasibility_for_display(result)
        )

        return NodeResult(
            node_name=self.name,
            status=status,
            output=result,
        )


class PatentResearchNode(WorkflowNode):
    """Patent Deep Research Node"""

    name = "patent_research"
    timeout_seconds = 300

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.patent_agent: PatentAgent | None = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("patent_research_executing", task_id=context.task_id)

        if self.patent_agent is None:
            from ...agents_extended.patent_agent import PatentAgent
            self.patent_agent = PatentAgent(self.llm_adapter)
            self.patent_agent.patent_skill = self.patent_agent._init_patent_skill()

        skill = cast(Any, self.patent_agent.patent_skill)
        topic = context.topic
        language = context.language

        result = await skill._deep_research(topic, language)

        # Save research result to workspace
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "patent_research.json",
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "patent_literature_review.txt",
            _format_research_for_display(result)
        )

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output=result,
        )


class PatentDraftingNode(WorkflowNode):
    """Patent Drafting Node (Claim-First)"""

    name = "patent_drafting"
    timeout_seconds = 180

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.patent_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("patent_drafting_executing", task_id=context.task_id)

        if self.patent_agent is None:
            from ...agents_extended.patent_agent import PatentAgent
            self.patent_agent = PatentAgent(self.llm_adapter)

        # Get research results from previous nodes
        feasibility = context.shared_data.get("patent_feasibility", {})
        research = context.shared_data.get("patent_research", {})

        agent_ctx = _create_agent_context(context)
        patent_content = await self.patent_agent._draft_patent_from_research(
            context=agent_ctx,
            feasibility=feasibility,
            research=research,
        )

        # Save patent draft to workspace
        _save_to_workspace(
            context.task_id,
            "writer_drafts",
            "patent_draft.json",
            json.dumps(patent_content.__dict__, ensure_ascii=False, indent=2)
        )

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output=patent_content.__dict__,
        )


class PatentValidationNode(WorkflowNode):
    """Patent Logic Validation Node"""

    name = "patent_validation"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.patent_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("patent_validation_executing", task_id=context.task_id)

        if self.patent_agent is None:
            from ...agents_extended.patent_agent import PatentAgent
            self.patent_agent = PatentAgent(self.llm_adapter)

        # Get patent content from previous node
        from ...skills.patent_writer import PatentContent
        patent_dict = context.shared_data.get("patent_drafting", {})
        patent = PatentContent(**patent_dict)

        result = await self.patent_agent._validate_logic(patent)

        status = NodeStatus.COMPLETED
        if result.get("status") == "FAIL":
            status = NodeStatus.FAILED

        # Save validation result to workspace
        _save_to_workspace(
            context.task_id,
            "reviewer_feedback",
            "patent_validation.json",
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "reviewer_feedback",
            "patent_validation_report.txt",
            _format_validation_for_display(result)
        )

        return NodeResult(
            node_name=self.name,
            status=status,
            output=result,
        )


class PatentPublishingNode(WorkflowNode):
    """Patent Publishing Node (.docx generation)"""

    name = "patent_publishing"
    timeout_seconds = 60

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.patent_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("patent_publishing_executing", task_id=context.task_id)

        if self.patent_agent is None:
            from ...agents_extended.patent_agent import PatentAgent
            self.patent_agent = PatentAgent(self.llm_adapter)

        # Get polished content from previous nodes
        from ...skills.patent_writer import PatentContent
        patent_dict = context.shared_data.get("patent_drafting", {})
        patent = PatentContent(**patent_dict)

        # Polish and publish
        polished = await self.patent_agent._polish(patent)
        agent_ctx = _create_agent_context(context)
        temp_output_path = await self.patent_agent._publish(polished, agent_ctx)

        # Move docx file to output directory for permanent storage
        temp_path = Path(temp_output_path)
        filename = temp_path.name
        doc_type_prefix = context.doc_type.lower() if context.doc_type else "patent"
        output_path = str(workspace_manager.move_to_output(
            task_id=context.task_id,
            filename=filename,
            output_dir_prefix=doc_type_prefix
        ))

        logger.info("patent_published", task_id=context.task_id, output_path=output_path)

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "output_path": output_path,
                "status": "published",
                "polished": polished.__dict__,
            },
        )


# Paper-specific nodes


class PaperFeasibilityNode(WorkflowNode):
    """Paper Feasibility Study Node"""

    name = "paper_feasibility"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.paper_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("paper_feasibility_executing", task_id=context.task_id)

        if self.paper_agent is None:
            from ...agents_extended.paper_agent import PaperAgent
            self.paper_agent = PaperAgent(self.llm_adapter)
            self.paper_agent.paper_skill = self.paper_agent._init_paper_skill()

        skill = cast(Any, self.paper_agent.paper_skill)
        topic = context.topic
        domain = context.domain
        language = context.language

        result = await skill._feasibility_study(topic, domain, language)

        status = NodeStatus.COMPLETED
        if result.get("feasibility") == "FAIL":
            status = NodeStatus.FAILED

        # Save feasibility result to workspace
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "paper_feasibility.json",
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "paper_feasibility_report.txt",
            _format_feasibility_for_display(result)
        )

        return NodeResult(
            node_name=self.name,
            status=status,
            output=result,
        )


class PaperResearchNode(WorkflowNode):
    """Paper Deep Research Node"""

    name = "paper_research"
    timeout_seconds = 300

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.paper_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("paper_research_executing", task_id=context.task_id)

        if self.paper_agent is None:
            from ...agents_extended.paper_agent import PaperAgent
            self.paper_agent = PaperAgent(self.llm_adapter)
            self.paper_agent.paper_skill = self.paper_agent._init_paper_skill()

        skill = cast(Any, self.paper_agent.paper_skill)
        topic = context.topic
        domain = context.domain
        language = context.language

        result = await skill._deep_research(topic, domain, language)

        # Save research result to workspace
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "paper_research.json",
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "investigation_results",
            "paper_literature_review.txt",
            _format_research_for_display(result)
        )

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output=result,
        )


class PaperDraftingNode(WorkflowNode):
    """Paper Drafting Node"""

    name = "paper_drafting"
    timeout_seconds = 180

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.paper_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("paper_drafting_executing", task_id=context.task_id)

        if self.paper_agent is None:
            from ...agents_extended.paper_agent import PaperAgent
            self.paper_agent = PaperAgent(self.llm_adapter)

        feasibility = context.shared_data.get("paper_feasibility", {})
        research = context.shared_data.get("paper_research", {})

        agent_ctx = _create_agent_context(context)
        paper_content = await self.paper_agent._draft_paper_from_research(
            context=agent_ctx,
            feasibility=feasibility,
            research=research,
        )

        # Save paper draft to workspace
        _save_to_workspace(
            context.task_id,
            "writer_drafts",
            "paper_draft.json",
            json.dumps(paper_content.__dict__, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "writer_drafts",
            "paper_draft.txt",
            _format_paper_content_for_display(paper_content.__dict__)
        )

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output=paper_content.__dict__,
        )


class PaperPublishingNode(WorkflowNode):
    """Paper Publishing Node (.docx generation)"""

    name = "paper_publishing"
    timeout_seconds = 60

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.paper_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("paper_publishing_executing", task_id=context.task_id)

        if self.paper_agent is None:
            from ...agents_extended.paper_agent import PaperAgent
            self.paper_agent = PaperAgent(self.llm_adapter)

        from ...skills.paper_writer import PaperContent
        paper_dict = context.shared_data.get("paper_drafting", {})
        paper = PaperContent(**paper_dict)

        language = context.language
        polished = await self.paper_agent._polish(paper, language)
        agent_ctx = _create_agent_context(context)
        temp_output_path = await self.paper_agent._publish(polished, agent_ctx)

        # Move docx file to output directory for permanent storage
        temp_path = Path(temp_output_path)
        filename = temp_path.name
        doc_type_prefix = context.doc_type.lower() if context.doc_type else "paper"
        output_path = str(workspace_manager.move_to_output(
            task_id=context.task_id,
            filename=filename,
            output_dir_prefix=doc_type_prefix
        ))

        logger.info("paper_published", task_id=context.task_id, output_path=output_path)

        # Save polished version to workspace
        _save_to_workspace(
            context.task_id,
            "writer_drafts",
            "paper_polished.json",
            json.dumps(polished.__dict__, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "writer_drafts",
            "paper_final.txt",
            _format_paper_content_for_display(polished.__dict__)
        )

        return NodeResult(
            node_name=self.name,
            status=NodeStatus.COMPLETED,
            output={
                "output_path": output_path,
                "status": "published",
                "polished": polished.__dict__,
            },
        )


def _format_paper_validation_for_display(result: dict[str, Any]) -> str:
    """Format paper validation result as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("PAPER VALIDATION REPORT")
    lines.append("=" * 60)
    lines.append(f"\nStatus: {result.get('status', 'UNKNOWN')}")

    logic = result.get("logic_validation", {})
    if logic:
        lines.append(f"\n--- Logic Validation ---")
        lines.append(f"Passed: {logic.get('passed', 'N/A')}")
        lines.append(f"Score: {logic.get('score', 'N/A')}")
        issues = logic.get("issues", [])
        if issues:
            lines.append("Issues:")
            for issue in issues:
                lines.append(f"  - {issue}")

    plagiarism = result.get("plagiarism_check", {})
    if plagiarism:
        lines.append(f"\n--- Plagiarism Check ---")
        lines.append(f"Passed: {plagiarism.get('passed', 'N/A')}")
        lines.append(f"Similarity Rate: {plagiarism.get('similarityRate', 'N/A')}%")

    innovation = result.get("innovationValidation", {})
    if innovation:
        lines.append(f"\n--- Innovation Validation ---")
        lines.append(f"Score: {innovation.get('score', 'N/A')}")
        lines.append(f"Type: {innovation.get('type', 'N/A')}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


class PaperValidationNode(WorkflowNode):
    """Paper Logic Validation Node"""

    name = "paper_validation"
    timeout_seconds = 120

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter
        self.paper_agent = None

    async def execute(self, context: WorkflowContext) -> NodeResult:
        from ...workflow.state_machine import NodeResult
        logger.info("paper_validation_executing", task_id=context.task_id)

        if self.paper_agent is None:
            from ...agents_extended.paper_agent import PaperAgent
            self.paper_agent = PaperAgent(self.llm_adapter)

        # Get paper content from previous node
        from ...skills.paper_writer import PaperContent
        paper_dict = context.shared_data.get("paper_drafting", {})
        paper = PaperContent(**paper_dict)

        result = await self.paper_agent._validate_logic(paper)

        status = NodeStatus.COMPLETED
        if result.get("status") == "FAIL":
            status = NodeStatus.FAILED

        # Save validation result to workspace
        _save_to_workspace(
            context.task_id,
            "reviewer_feedback",
            "paper_validation.json",
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        _save_to_workspace(
            context.task_id,
            "reviewer_feedback",
            "paper_validation_report.txt",
            _format_paper_validation_for_display(result)
        )

        return NodeResult(
            node_name=self.name,
            status=status,
            output=result,
        )


# Extended node registry
EXTENDED_NODES = {
    # Patent nodes
    "patent_feasibility": PatentFeasibilityNode,
    "patent_research": PatentResearchNode,
    "patent_drafting": PatentDraftingNode,
    "patent_validation": PatentValidationNode,
    "patent_publishing": PatentPublishingNode,
    # Paper nodes
    "paper_feasibility": PaperFeasibilityNode,
    "paper_research": PaperResearchNode,
    "paper_drafting": PaperDraftingNode,
    "paper_validation": PaperValidationNode,
    "paper_publishing": PaperPublishingNode,
}
