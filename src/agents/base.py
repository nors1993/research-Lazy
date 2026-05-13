"""Base agent class for all AI agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..llm.adapter import BaseLLMAdapter, LLMProvider, LLMResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AgentRole(StrEnum):
    """Agent role enumeration."""

    EDITOR = "editor"
    INVESTIGATOR = "investigator"
    WRITER = "writer"
    REVIEWER = "reviewer"


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    role: AgentRole
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 16384
    provider: LLMProvider = LLMProvider.OPENAI
    system_prompt: str = ""


@dataclass
class AgentContext:
    """Context passed to agents during execution."""

    task_id: str
    topic: str
    domain: str
    doc_type: str
    requirements: str | None = None
    template_path: str | None = None
    template_content: str | None = None
    temp_prompt: str | None = None
    attachment_content: str | None = None
    shared_data: dict = field(default_factory=dict)
    language: str = "zh-CN"  # Language for document generation, default to Chinese


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, config: AgentConfig, llm_adapter: BaseLLMAdapter):
        self.config = config
        self.llm_adapter = llm_adapter
        self.role = config.role

    @abstractmethod
    async def execute(self, context: AgentContext) -> dict[str, Any]:
        """
        Execute the agent's task.

        Args:
            context: The execution context containing task details

        Returns:
            A dictionary containing the execution results
        """
        pass

    async def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a response using the LLM."""
        full_system_prompt = system_prompt or self.config.system_prompt

        logger.info(
            "llm_request",
            role=self.role.value,
            model=self.config.model,
            prompt_length=len(prompt),
        )

        response = await self.llm_adapter.generate(
            prompt=prompt,
            system_prompt=full_system_prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        logger.info(
            "llm_response",
            role=self.role.value,
            tokens_used=response.tokens_used,
            content_length=len(response.content),
        )

        return response

    async def stream_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ):
        """Stream a response using the LLM."""
        full_system_prompt = system_prompt or self.config.system_prompt

        logger.info(
            "llm_stream_request",
            role=self.role.value,
            model=self.config.model,
            prompt_length=len(prompt),
        )

        async for chunk in self.llm_adapter.stream_generate(  # type: ignore
            prompt=prompt,
            system_prompt=full_system_prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ):
            yield chunk

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(role={self.role.value}, model={self.config.model})>"
