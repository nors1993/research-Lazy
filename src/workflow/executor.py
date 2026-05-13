"""Workflow executor service."""

import asyncio
from datetime import UTC, datetime

from ..agents.base import AgentContext
from ..agents.editor import EditorAgent
from ..agents.investigator import InvestigatorAgent
from ..agents.reviewer import ReviewerAgent
from ..agents.writer import WriterAgent
from ..config import settings
from ..llm.adapter import LLMAdapter, LLMProvider
from ..utils.logger import get_logger

logger = get_logger(__name__)


# Node timeout configuration (seconds) - matched to realistic LLM call durations
NODE_TIMEOUTS = {
    "intent_analysis": 60,
    "feasibility_study": 120,
    "deep_research": 300,  # Literature review can be long
    "drafting": 600,  # Writing full paper takes time
    "logic_validation": 120,
    "plagiarism_check": 60,
    "polishing": 300,
    "publishing": 30,
}


def _provider_to_enum(provider: str) -> LLMProvider:
    """Convert provider string to LLMProvider enum."""
    provider = provider.lower()
    if provider in ["openai_compatible", "openai-compatible"]:
        return LLMProvider.OPENAI_COMPATIBLE
    elif provider == "anthropic":
        return LLMProvider.ANTHROPIC
    elif provider == "azure" or provider == "azure_openai":
        return LLMProvider.AZURE_OPENAI
    elif provider == "ollama":
        return LLMProvider.OLLAMA
    else:
        logger.warning("unknown_provider_defaulting_to_openai", provider=provider)
        return LLMProvider.OPENAI


def create_agent_adapter(agent_name: str):
    """Create LLM adapter for a specific agent based on configuration."""
    config = settings.get_agent_config(agent_name)

    # Build kwargs
    kwargs = {
        "api_key": config.api_key,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    # Add base_url for compatible providers
    if config.base_url and config.provider in ["openai_compatible", "openai-compatible"]:
        base_url = config.base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = base_url + "/v1"
        kwargs["base_url"] = base_url

    # Get provider enum
    provider = _provider_to_enum(config.provider)

    logger.info(
        "creating_agent_adapter",
        agent=agent_name,
        provider=provider.value,
        model=config.model,
    )

    return LLMAdapter.create(
        provider=provider,
        model=config.model,
        **kwargs
    )


async def _call_with_timeout(coro, timeout_seconds: int, node_name: str):
    """Execute coroutine with timeout, raising TimeoutError on timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError:
        logger.warning("node_timeout", node=node_name, timeout=timeout_seconds)
        raise TimeoutError(f"Node {node_name} timed out after {timeout_seconds}s")


class WorkflowExecutor:
    """Executes the research workflow."""

    def __init__(
        self,
        editor_adapter=None,
        investigator_adapter=None,
        writer_adapter=None,
        reviewer_adapter=None,
    ):
        # Create adapters for each agent if not provided
        self.editor_adapter = editor_adapter or create_agent_adapter("editor")
        self.investigator_adapter = investigator_adapter or create_agent_adapter("investigator")
        self.writer_adapter = writer_adapter or create_agent_adapter("writer")
        self.reviewer_adapter = reviewer_adapter or create_agent_adapter("reviewer")

        # Get agent configs from settings
        editor_config = settings.get_agent_config("editor")
        investigator_config = settings.get_agent_config("investigator")
        writer_config = settings.get_agent_config("writer")
        reviewer_config = settings.get_agent_config("reviewer")

        # Create agents with their respective adapters and configs
        self.editor = EditorAgent(
            self.editor_adapter,
            model=editor_config.model,
            temperature=editor_config.temperature,
            max_tokens=editor_config.max_tokens,
        )
        self.investigator = InvestigatorAgent(
            self.investigator_adapter,
            model=investigator_config.model,
            temperature=investigator_config.temperature,
            max_tokens=investigator_config.max_tokens,
        )
        self.writer = WriterAgent(
            self.writer_adapter,
            model=writer_config.model,
            temperature=writer_config.temperature,
            max_tokens=writer_config.max_tokens,
        )
        self.reviewer = ReviewerAgent(
            self.reviewer_adapter,
            model=reviewer_config.model,
            temperature=reviewer_config.temperature,
            max_tokens=reviewer_config.max_tokens,
        )

        # Get individual step timeouts from config
        self.step_timeouts = {
            "intent_analysis": NODE_TIMEOUTS.get("intent_analysis", 60),
            "feasibility_study": NODE_TIMEOUTS.get("feasibility_study", 120),
            "deep_research": NODE_TIMEOUTS.get("deep_research", 300),
            "drafting": NODE_TIMEOUTS.get("drafting", 600),
            "logic_validation": NODE_TIMEOUTS.get("logic_validation", 120),
            "plagiarism_check": NODE_TIMEOUTS.get("plagiarism_check", 60),
            "polishing": NODE_TIMEOUTS.get("polishing", 300),
            "publishing": NODE_TIMEOUTS.get("publishing", 30),
        }

    async def _step_with_timeout(self, coro, step_name: str) -> dict:
        """Execute a step with timeout protection."""
        timeout = self.step_timeouts.get(step_name, 300)
        try:
            return await _call_with_timeout(coro, timeout, step_name)
        except TimeoutError:
            logger.error("step_timeout", step=step_name, timeout=timeout)
            raise

    async def execute_task(
        self,
        task_id: str,
        topic: str,
        domain: str,
        doc_type: str,
        requirements: str | None = None,
        template_path: str | None = None,
        template_content: str | None = None,
        temp_prompt: str | None = None,
        attachment_content: str | None = None,
    ) -> dict:
        """Execute the full research workflow."""

        logger.info("workflow_started", task_id=task_id, topic=topic)

        # Create agent context
        context = AgentContext(
            task_id=task_id,
            topic=topic,
            doc_type=doc_type,
            domain=domain,
            requirements=requirements,
            template_path=template_path,
            template_content=template_content,
            temp_prompt=temp_prompt,
            attachment_content=attachment_content,
        )

        try:
            # Pass sub-agents' adapters to the editor for workflow execution
            result = await self.editor.execute_workflow(
                context,
                investigator_adapter=self.investigator_adapter,
                writer_adapter=self.writer_adapter,
                reviewer_adapter=self.reviewer_adapter,
            )

            logger.info("workflow_completed", task_id=task_id, status=result.get('status'))

            # Return proper status based on workflow result
            workflow_status = result.get("status", "failed")
            if workflow_status == "completed":
                return_status = "COMPLETED"
            else:
                return_status = "FAILED"

            return {
                "status": return_status,
                "output": result,
                "completed_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error("workflow_failed", task_id=task_id, error=str(e))
            return {
                "status": "FAILED",
                "error": str(e),
                "failed_at": datetime.now(UTC).isoformat(),
            }


def create_llm_adapter():
    """Create LLM adapter based on configuration (legacy function for compatibility)."""
    # Check for OpenAI Compatible first
    if settings.openai_compatible_api_key and settings.openai_compatible_base_url:
        base_url = settings.openai_compatible_base_url.rstrip("/")
        # Add /v1 only if not already present
        if not base_url.endswith("/v1"):
            base_url = base_url + "/v1"
        return LLMAdapter.create(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model=settings.openai_compatible_model or "deepseek-chat",
            api_key=settings.openai_compatible_api_key,
            base_url=base_url,
        )
    # Fall back to standard OpenAI
    elif settings.openai_api_key:
        return LLMAdapter.create(
            provider=LLMProvider.OPENAI,
            model="gpt-4o",
            api_key=settings.openai_api_key,
        )
    else:
        raise ValueError("No LLM provider configured")


# Global executor instance
_workflow_executor: WorkflowExecutor | None = None


def get_workflow_executor() -> WorkflowExecutor:
    """Get or create workflow executor with per-agent adapters."""
    global _workflow_executor
    if _workflow_executor is None:
        _workflow_executor = WorkflowExecutor()
    return _workflow_executor
