"""Unified LLM adapter interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"  # For custom base_url endpoints
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    model: str
    tokens_used: int | None = None
    raw_response: dict | None = None


@dataclass
class LLMChunk:
    """Streaming chunk response."""

    content: str
    model: str


class BaseLLMAdapter(ABC):
    """Abstract base class for LLM adapters."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_kwargs = kwargs

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from the LLM."""

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """Stream generate responses from the LLM."""
        # Default implementation - must be overridden by subclasses
        # Subclasses should use @abstractmethod decorator
        raise NotImplementedError("Subclass must implement stream_generate")

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate API key and connection."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(provider={self.provider}, model={self.model})>"


class LLMAdapter:
    """Factory for creating LLM adapters."""

    _adapters: dict[LLMProvider, type[BaseLLMAdapter]] = {}

    @classmethod
    def register(cls, provider: LLMProvider, adapter_class: type[BaseLLMAdapter]) -> None:
        """Register an adapter for a provider."""
        cls._adapters[provider] = adapter_class

    @classmethod
    def create(
        cls,
        provider: LLMProvider,
        model: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> BaseLLMAdapter:
        """Create an LLM adapter instance."""
        if provider not in cls._adapters:
            raise ValueError(f"No adapter registered for provider: {provider}")

        adapter_class = cls._adapters[provider]
        return adapter_class(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    @classmethod
    def get_default_config(cls, provider: LLMProvider) -> dict[str, Any]:
        """Get default configuration for a provider."""
        configs = {
            LLMProvider.OPENAI: {
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 16384,
            },
            LLMProvider.OPENAI_COMPATIBLE: {
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 16384,
                "base_url": None,  # Must be set by user
            },
            LLMProvider.ANTHROPIC: {
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.7,
                "max_tokens": 16384,
            },
            LLMProvider.AZURE_OPENAI: {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 16384,
            },
            LLMProvider.OLLAMA: {
                "model": "llama2",
                "temperature": 0.7,
                "max_tokens": 16384,
            },
        }
        return configs.get(provider, {})


# Import and register adapters
from .providers.anthropic import AnthropicAdapter  # noqa: E402
from .providers.azure import AzureAdapter  # noqa: E402
from .providers.ollama import OllamaAdapter  # noqa: E402
from .providers.openai import OpenAIAdapter  # noqa: E402

LLMAdapter.register(LLMProvider.OPENAI, OpenAIAdapter)
LLMAdapter.register(LLMProvider.OPENAI_COMPATIBLE, OpenAIAdapter)
LLMAdapter.register(LLMProvider.ANTHROPIC, AnthropicAdapter)
LLMAdapter.register(LLMProvider.AZURE_OPENAI, AzureAdapter)
LLMAdapter.register(LLMProvider.OLLAMA, OllamaAdapter)
