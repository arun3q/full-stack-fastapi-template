"""AI / LLM provider abstraction.

Supports OpenAI-compatible APIs (OpenAI, Groq, Ollama, vLLM, ...) and Anthropic.
Set ``AI_PROVIDER`` to ``openai`` or ``anthropic`` and provide the matching API
key in the environment. ``get_ai_provider()`` returns ``None`` when disabled.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, cast

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """Raised when the configured AI provider is not available."""


class AIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield incremental response text tokens."""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return provider diagnostics (name, model, configured)."""


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise AIProviderError("OPENAI_API_KEY is not configured")
        from openai import AsyncOpenAI

        self.model = settings.OPENAI_MODEL
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

    async def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        api_messages: list[dict[str, str]] = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)
        stream: Any = await self._client.chat.completions.create(
            model=self.model,
            messages=cast(Any, api_messages),
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "base_url": str(settings.OPENAI_BASE_URL or "https://api.openai.com"),
            "configured": True,
        }


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise AIProviderError("ANTHROPIC_API_KEY is not configured")
        from anthropic import AsyncAnthropic

        self.model = settings.ANTHROPIC_MODEL
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def health(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "configured": True,
        }


def get_ai_provider() -> AIProvider | None:
    if settings.AI_PROVIDER == "openai":
        try:
            return OpenAIProvider()
        except AIProviderError:
            logger.warning("AI provider 'openai' not configured")
            return None
    if settings.AI_PROVIDER == "anthropic":
        try:
            return AnthropicProvider()
        except AIProviderError:
            logger.warning("AI provider 'anthropic' not configured")
            return None
    return None
