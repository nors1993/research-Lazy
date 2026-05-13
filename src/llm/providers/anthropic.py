"""Anthropic LLM adapter implementation."""

from collections.abc import AsyncIterator
from typing import Any

import anthropic

from ...utils.exceptions import LLMAPIKeyError, LLMResponseError
from ..adapter import (
    BaseLLMAdapter,
    LLMAdapter,
    LLMChunk,
    LLMProvider,
    LLMResponse,
)


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic LLM adapter using the Anthropic SDK."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ):
        super().__init__(
            provider=provider,
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=kwargs.get("timeout", 60),
            max_retries=kwargs.get("max_retries", 3),
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from Anthropic."""
        if not self.api_key:
            raise LLMAPIKeyError("Anthropic")

        messages = [{"role": "user", "content": prompt}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})

        try:
            response = await self._client.messages.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                system=system_prompt,
            )

            content = response.content[0].text if response.content else ""

            return LLMResponse(
                content=content,
                model=response.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else None,
            )

        except anthropic.AuthenticationError as e:
            raise LLMAPIKeyError("Anthropic") from e
        except anthropic.APIError as e:
            raise LLMResponseError(str(e)) from e
        except Exception as e:
            raise LLMResponseError(f"Unexpected error: {str(e)}") from e

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """Stream generate responses from Anthropic."""
        if not self.api_key:
            raise LLMAPIKeyError("Anthropic")

        messages = [{"role": "user", "content": prompt}]

        try:
            async with self._client.messages.stream(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                system=system_prompt,
            ) as stream:
                async for text in stream.text_stream:
                    yield LLMChunk(content=text, model=self.model)

        except anthropic.AuthenticationError as e:
            raise LLMAPIKeyError("Anthropic") from e
        except Exception as e:
            raise LLMResponseError(f"Unexpected error: {str(e)}") from e

    async def validate_connection(self) -> bool:
        """Validate Anthropic API key."""
        if not self.api_key:
            return False
        try:
            await self._client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception:
            return False


# Register with the adapter factory
LLMAdapter.register(LLMProvider.ANTHROPIC, AnthropicAdapter)
