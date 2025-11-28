"""Provider-agnostic LLM client factory for the Rodin Frame Engine.

This module provides a unified interface to create LLM clients from different
providers (Google, OpenAI, Anthropic) based on configuration.
"""
import os
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel


class LLMConfigError(ValueError):
    """Raised when the LLM configuration is invalid or incomplete."""
    pass


def get_llm_client(
    provider: str,
    model_name: str,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """Creates and returns a LangChain chat model client for the specified provider.

    This factory function abstracts away provider-specific initialization,
    allowing the Frame Engine to work with any supported LLM provider.

    Args:
        provider: The LLM provider to use. Supported values: "google", "openai", "anthropic".
        model_name: The name of the model to use (provider-specific).
        temperature: Optional temperature setting for response randomness (0.0 to 1.0).

    Returns:
        An instance of a LangChain `BaseChatModel` configured for the specified provider.

    Raises:
        LLMConfigError: If the provider is not supported or required environment
            variables are missing.
    """
    provider = provider.lower()

    if provider == 'google':
        return _create_google_client(model_name, temperature)
    elif provider == 'openai':
        return _create_openai_client(model_name, temperature)
    elif provider == 'anthropic':
        return _create_anthropic_client(model_name, temperature)
    else:
        raise LLMConfigError(
            f"Unsupported LLM provider: '{provider}'. "
            "Supported providers: 'google', 'openai', 'anthropic'."
        )


def _create_google_client(model_name: str, temperature: Optional[float]) -> BaseChatModel:
    """Creates a Google Gemini LLM client."""
    _require_env_var('GOOGLE_API_KEY', 'Google Gemini')

    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, Any] = {'model': model_name}
    if temperature is not None:
        kwargs['temperature'] = temperature

    return ChatGoogleGenerativeAI(**kwargs)


def _create_openai_client(model_name: str, temperature: Optional[float]) -> BaseChatModel:
    """Creates an OpenAI LLM client."""
    _require_env_var('OPENAI_API_KEY', 'OpenAI')

    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {'model': model_name}
    if temperature is not None:
        kwargs['temperature'] = temperature

    return ChatOpenAI(**kwargs)


def _create_anthropic_client(model_name: str, temperature: Optional[float]) -> BaseChatModel:
    """Creates an Anthropic Claude LLM client."""
    _require_env_var('ANTHROPIC_API_KEY', 'Anthropic')

    from langchain_anthropic import ChatAnthropic

    kwargs: dict[str, Any] = {'model': model_name}
    if temperature is not None:
        kwargs['temperature'] = temperature

    return ChatAnthropic(**kwargs)


def _require_env_var(var_name: str, provider_name: str) -> None:
    """Checks that a required environment variable is set.

    Args:
        var_name: The name of the environment variable.
        provider_name: The name of the provider (for error messages).

    Raises:
        LLMConfigError: If the environment variable is not set.
    """
    if var_name not in os.environ:
        raise LLMConfigError(
            f"{var_name} environment variable not set. "
            f"Please set it in scripts/.env to use {provider_name}."
        )
