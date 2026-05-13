"""Azure OpenAI LLM adapter implementation."""

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncAzureOpenAI

from ...utils.exceptions import LLMAPIKeyError, LLMResponseError
from ..adapter import (
    BaseLLMAdapter,
    LLMAdapter,
    LLMChunk,
    LLMProvider,
    LLMResponse,
)


class AzureAdapter(BaseLLMAdapter):
    """Azure OpenAI LLM adapter."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_base: str | None = None,
        api_version: str = "2024-02-01",
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
        self._api_base = api_base
        self._api_version = api_version

        self._client = AsyncAzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=api_base or "",
            timeout=kwargs.get("timeout", 60),
            max_retries=kwargs.get("max_retries", 3),
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from Azure OpenAI."""
        if not self.api_key:
            raise LLMAPIKeyError("Azure")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )

            content = response.choices[0].message.content or ""

            return LLMResponse(
                content=content,
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else None,
            )

        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower():
                raise LLMAPIKeyError("Azure") from e
            raise LLMResponseError(error_msg) from e

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """Stream generate responses from Azure OpenAI."""
        if not self.api_key:
            raise LLMAPIKeyError("Azure")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield LLMChunk(
                        content=chunk.choices[0].delta.content,
                        model=self.model,
                    )

        except Exception as e:
            raise LLMResponseError(str(e)) from e

    async def validate_connection(self) -> bool:
        """Validate Azure API key."""
        if not self.api_key:
            return False
        try:
            await self._client.chat.completions.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception:
            return False


# Register with the adapter factory
LLMAdapter.register(LLMProvider.AZURE_OPENAI, AzureAdapter)
