"""Tests for the LLM provider module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gse_guides.enrichment.llm_provider import (
    AnthropicProvider,
    LLMProvider,
    OpenAIProvider,
    create_provider,
)


class TestCreateProvider:
    """Tests for the create_provider factory."""

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider("invalid")

    def test_anthropic_missing_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises((ValueError, ImportError)):
                create_provider("anthropic", api_key="")

    def test_openai_missing_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises((ValueError, ImportError)):
                create_provider("openai", api_key="")


class TestAnthropicProvider:
    """Tests for AnthropicProvider with mocked SDK."""

    @pytest.fixture
    def mock_anthropic(self):
        """Fixture that mocks the anthropic module."""
        mock_module = MagicMock()

        # Mock client and response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"summary": "test"}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_module.Anthropic.return_value.messages.create.return_value = mock_response

        return mock_module

    def test_complete_returns_text_and_tokens(self, mock_anthropic):
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="test-key")
            text, tokens = provider.complete("test prompt", system="system")

        assert text == '{"summary": "test"}'
        assert tokens == 150

    def test_model_name_default(self, mock_anthropic):
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="test-key")
        assert provider.model_name == "claude-haiku-4-20250414"

    def test_model_name_custom(self, mock_anthropic):
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(model="claude-sonnet-4-20250514", api_key="test-key")
        assert provider.model_name == "claude-sonnet-4-20250514"

    def test_estimate_cost(self, mock_anthropic):
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="test-key")
        cost = provider.estimate_cost(1000, 1000)
        assert cost > 0
        assert isinstance(cost, float)

    def test_cost_properties(self, mock_anthropic):
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="test-key")
        assert provider.cost_per_1k_input_tokens == 0.00025
        assert provider.cost_per_1k_output_tokens == 0.00125

    def test_complete_with_system_prompt(self, mock_anthropic):
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = AnthropicProvider(api_key="test-key")
            provider.complete("prompt", system="be helpful")

        call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args
        assert call_kwargs.kwargs.get("system") == "be helpful"


class TestOpenAIProvider:
    """Tests for OpenAIProvider with mocked SDK."""

    @pytest.fixture
    def mock_openai(self):
        """Fixture that mocks the openai module."""
        mock_module = MagicMock()

        mock_choice = MagicMock()
        mock_choice.message.content = '{"summary": "openai test"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.total_tokens = 200
        mock_module.OpenAI.return_value.chat.completions.create.return_value = mock_response

        return mock_module

    def test_complete_returns_text_and_tokens(self, mock_openai):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="test-key")
            text, tokens = provider.complete("test prompt")

        assert text == '{"summary": "openai test"}'
        assert tokens == 200

    def test_model_name_default(self, mock_openai):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="test-key")
        assert provider.model_name == "gpt-4o-mini"

    def test_cost_properties(self, mock_openai):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="test-key")
        assert provider.cost_per_1k_input_tokens == 0.00015
        assert provider.cost_per_1k_output_tokens == 0.0006

    def test_system_message_included(self, mock_openai):
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = OpenAIProvider(api_key="test-key")
            provider.complete("prompt", system="be helpful")

        call_kwargs = mock_openai.OpenAI.return_value.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages", [])
        assert any(m.get("role") == "system" for m in messages)


class TestLLMProviderABC:
    """Tests for the abstract base class contract."""

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]
