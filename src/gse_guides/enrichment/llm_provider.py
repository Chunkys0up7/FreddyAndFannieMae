"""Abstract LLM provider interface with Anthropic and OpenAI implementations."""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract interface for LLM API calls."""

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> tuple[str, int]:
        """Send a prompt and return (completion_text, tokens_used)."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...

    @property
    @abstractmethod
    def cost_per_1k_input_tokens(self) -> float:
        ...

    @property
    @abstractmethod
    def cost_per_1k_output_tokens(self) -> float:
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost for a given token count."""
        return (
            (input_tokens / 1000) * self.cost_per_1k_input_tokens
            + (output_tokens / 1000) * self.cost_per_1k_output_tokens
        )


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    DEFAULT_MODEL = "claude-haiku-4-20250414"

    # Pricing per 1K tokens (as of 2026)
    PRICING = {
        "claude-haiku-4-20250414": (0.00025, 0.00125),
        "claude-sonnet-4-20250514": (0.003, 0.015),
        "claude-opus-4-20250514": (0.015, 0.075),
    }

    def __init__(
        self,
        model: str = "",
        api_key: str | None = None,
        max_retries: int = 3,
        timeout: int = 60,
    ):
        self._model = model or self.DEFAULT_MODEL
        self._max_retries = max_retries
        self._timeout = timeout

        try:
            import anthropic  # noqa: F811
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for Anthropic LLM enrichment. "
                "Install it with: pip install -e '.[llm]'"
            )

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self._client = anthropic.Anthropic(api_key=key, timeout=timeout)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return self.PRICING.get(self._model, (0.00025, 0.00125))[0]

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return self.PRICING.get(self._model, (0.00025, 0.00125))[1]

    def complete(self, prompt: str, system: str = "") -> tuple[str, int]:
        """Call Anthropic Messages API with retry logic."""
        last_error = None

        for attempt in range(self._max_retries + 1):
            try:
                kwargs: dict = {
                    "model": self._model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if system:
                    kwargs["system"] = system

                response = self._client.messages.create(**kwargs)

                text = response.content[0].text if response.content else ""
                tokens = (response.usage.input_tokens or 0) + (
                    response.usage.output_tokens or 0
                )
                return text, tokens

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # Retry on rate limit and server errors
                if any(
                    kw in error_str
                    for kw in ("rate_limit", "overloaded", "529", "500", "503")
                ):
                    delay = (2**attempt) + 1
                    logger.warning(
                        "Anthropic API error (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        self._max_retries + 1,
                        str(e)[:100],
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise

        raise last_error  # type: ignore[misc]


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    DEFAULT_MODEL = "gpt-4o-mini"

    PRICING = {
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4o": (0.0025, 0.01),
    }

    def __init__(
        self,
        model: str = "",
        api_key: str | None = None,
        max_retries: int = 3,
        timeout: int = 60,
    ):
        self._model = model or self.DEFAULT_MODEL
        self._max_retries = max_retries
        self._timeout = timeout

        try:
            import openai  # noqa: F811
        except ImportError:
            raise ImportError(
                "The 'openai' package is required for OpenAI LLM enrichment. "
                "Install it with: pip install -e '.[llm]'"
            )

        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self._client = openai.OpenAI(api_key=key, timeout=timeout)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return self.PRICING.get(self._model, (0.00015, 0.0006))[0]

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return self.PRICING.get(self._model, (0.00015, 0.0006))[1]

    def complete(self, prompt: str, system: str = "") -> tuple[str, int]:
        """Call OpenAI Chat Completions API with retry logic."""
        last_error = None

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.0,
                )

                text = response.choices[0].message.content or "" if response.choices else ""
                tokens = response.usage.total_tokens if response.usage else 0
                return text, tokens

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if any(
                    kw in error_str
                    for kw in ("rate_limit", "429", "500", "503", "overloaded")
                ):
                    delay = (2**attempt) + 1
                    logger.warning(
                        "OpenAI API error (attempt %d/%d): %s. Retrying in %ds...",
                        attempt + 1,
                        self._max_retries + 1,
                        str(e)[:100],
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise

        raise last_error  # type: ignore[misc]


def create_provider(
    provider_name: str,
    model: str = "",
    api_key: str | None = None,
    max_retries: int = 3,
    timeout: int = 60,
) -> LLMProvider:
    """Factory function to create an LLM provider by name.

    Args:
        provider_name: "anthropic" or "openai"
        model: Model override (empty = provider default)
        api_key: API key (None = read from environment)
        max_retries: Max retry attempts on transient errors
        timeout: Request timeout in seconds
    """
    if provider_name == "anthropic":
        return AnthropicProvider(
            model=model, api_key=api_key,
            max_retries=max_retries, timeout=timeout,
        )
    elif provider_name == "openai":
        return OpenAIProvider(
            model=model, api_key=api_key,
            max_retries=max_retries, timeout=timeout,
        )
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name!r}. "
            f"Supported: 'anthropic', 'openai'"
        )
