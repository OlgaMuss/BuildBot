"""Tests for the LLM client factory.

These tests verify:
- US8: LLM Provider Configuration
"""
import os

import pytest

from backend.frame_engine.llm import LLMConfigError, get_llm_client


@pytest.fixture(scope='session')
def config(test_config):
    """Provides the test configuration with a shorter name for convenience."""
    return test_config


class TestLLMProviderConfiguration:
    """Tests for US8: LLM Provider Configuration."""

    def test_llm_provider_google(self, config):
        """Verifies that Google provider can be instantiated.

        US8: Provider is specified in config.yaml.
        """
        # Skip if no API key is available
        if 'GOOGLE_API_KEY' not in os.environ:
            pytest.skip('GOOGLE_API_KEY not set')

        llm_config = config.get('llm', {})
        client = get_llm_client(
            provider='google',
            model_name=llm_config.get('model_name', 'gemini-2.5-flash-lite'),
        )

        assert client is not None
        # Verify it's the correct type
        assert 'Google' in type(client).__name__ or 'Gemini' in type(client).__name__

    def test_llm_missing_api_key(self, monkeypatch):
        """Verifies that missing API key raises LLMConfigError.

        US8: Missing API key raises LLMConfigError with clear message.
        """
        # Remove the API key from environment
        monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

        with pytest.raises(LLMConfigError) as exc_info:
            get_llm_client(provider='google', model_name='gemini-2.5-flash-lite')

        assert 'GOOGLE_API_KEY' in str(exc_info.value)

    def test_llm_unsupported_provider(self):
        """Verifies that unsupported provider raises LLMConfigError.

        US8: Invalid provider is rejected with clear error.
        """
        with pytest.raises(LLMConfigError) as exc_info:
            get_llm_client(provider='invalid_provider', model_name='some-model')

        assert 'Unsupported' in str(exc_info.value)
        assert 'invalid_provider' in str(exc_info.value)

    def test_llm_temperature_optional(self, config):
        """Verifies that temperature parameter is optional.

        US8: Temperature is optional.
        """
        if 'GOOGLE_API_KEY' not in os.environ:
            pytest.skip('GOOGLE_API_KEY not set')

        # Without temperature
        client_no_temp = get_llm_client(
            provider='google',
            model_name='gemini-2.5-flash-lite',
        )
        assert client_no_temp is not None

        # With temperature
        client_with_temp = get_llm_client(
            provider='google',
            model_name='gemini-2.5-flash-lite',
            temperature=0.7,
        )
        assert client_with_temp is not None


class TestLLMActualCalls:
    """Tests that verify actual LLM calls work correctly."""

    @pytest.mark.asyncio
    async def test_llm_simple_call(self, llm_client):
        """Verifies that a simple LLM call returns a response.

        This uses actual LLM calls (no mocking).
        """
        from langchain_core.messages import HumanMessage

        messages = [HumanMessage(content='Say "hello" and nothing else.')]
        response = await llm_client.ainvoke(messages)

        # Should get a response with content
        content = getattr(response, 'content', '')
        assert content != ''
        assert 'hello' in content.lower()

