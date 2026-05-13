"""OpenAI LLM adapter implementation."""

from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI

from ...utils.exceptions import LLMAPIKeyError, LLMResponseError
from ..adapter import (
    BaseLLMAdapter,
    LLMAdapter,
    LLMChunk,
    LLMProvider,
    LLMResponse,
)


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI LLM adapter using the OpenAI SDK.
    
    Supports standard OpenAI API and OpenAI-compatible APIs (custom base_url).
    """

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        base_url: str | None = None,
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
        self._base_url = base_url

        # Build client kwargs
        client_kwargs = {
            "api_key": api_key,
            "timeout": kwargs.get("timeout", 300),  # 5 minutes for long paper generation
            "max_retries": kwargs.get("max_retries", 5),  # More retries for robustness
        }

        # Add custom base_url for OpenAI-compatible APIs
        if base_url:
            # Don't add /v1 - user should provide complete URL or adapter should handle it
            client_kwargs["base_url"] = base_url.rstrip("/")

        self._client = AsyncOpenAI(**client_kwargs)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from OpenAI."""
        if not self.api_key:
            raise LLMAPIKeyError("OpenAI")

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
                stream=False,
            )

            content = response.choices[0].message.content or ""

            return LLMResponse(
                content=content,
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else None,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

        except openai.AuthenticationError as e:
            raise LLMAPIKeyError("OpenAI") from e
        except (openai.APIError, openai.NotFoundError) as e:
            raise LLMResponseError(str(e)) from e
        except Exception as e:
            raise LLMResponseError(f"Unexpected error: {str(e)}") from e

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """Stream generate responses from OpenAI."""
        if not self.api_key:
            raise LLMAPIKeyError("OpenAI")

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
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield LLMChunk(
                        content=chunk.choices[0].delta.content,
                        model=chunk.model,
                    )

        except openai.APIAuthenticationError as e:
            raise LLMAPIKeyError("OpenAI") from e
        except openai.APIError as e:
            raise LLMResponseError(str(e)) from e
        except Exception as e:
            raise LLMResponseError(f"Unexpected error: {str(e)}") from e

    async def validate_connection(self) -> bool:
        """Validate OpenAI API key."""
        if not self.api_key:
            return False
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the client connection."""
        await self._client.close()


# Register with the adapter factory
LLMAdapter.register(LLMProvider.OPENAI, OpenAIAdapter)
LLMAdapter.register(LLMProvider.OPENAI_COMPATIBLE, OpenAIAdapter)
