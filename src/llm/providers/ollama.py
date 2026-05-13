"""Ollama LLM adapter implementation (local models)."""

from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from ...utils.exceptions import LLMResponseError
from ..adapter import (
    BaseLLMAdapter,
    LLMAdapter,
    LLMChunk,
    LLMProvider,
    LLMResponse,
)


class OllamaAdapter(BaseLLMAdapter):
    """Ollama LLM adapter for local models."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        api_key: str = "",  # Ollama typically doesn't need API key
        temperature: float = 0.7,
        max_tokens: int = 4096,
        base_url: str = "http://localhost:11434",
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
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=kwargs.get("timeout", 120))

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "options": {
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise LLMResponseError(f"Ollama error: {error_text}")

                    result = await response.json()
                    content = result.get("response", "")

                    return LLMResponse(
                        content=content,
                        model=self.model,
                        tokens_used=None,  # Ollama doesn't provide token counts
                    )

        except aiohttp.ClientError as e:
            raise LLMResponseError(f"Connection error: {str(e)}") from e

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMChunk]:
        """Stream generate responses from Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "options": {
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
            },
            "stream": True,
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise LLMResponseError(f"Ollama error: {error_text}")

                    async for line in response.content:
                        if line:
                            try:
                                import json
                                data = json.loads(line)
                                if "response" in data:
                                    yield LLMChunk(
                                        content=data["response"],
                                        model=self.model,
                                    )
                            except json.JSONDecodeError:
                                continue

        except aiohttp.ClientError as e:
            raise LLMResponseError(f"Connection error: {str(e)}") from e

    async def validate_connection(self) -> bool:
        """Validate Ollama server is running."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self._base_url}/api/tags") as response:
                    return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models on Ollama server."""
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(f"{self._base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return [m["name"] for m in data.get("models", [])]
                    return []
        except Exception:
            return []


# Register with the adapter factory
LLMAdapter.register(LLMProvider.OLLAMA, OllamaAdapter)
