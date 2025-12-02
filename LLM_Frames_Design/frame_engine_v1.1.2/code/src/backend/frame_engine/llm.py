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


def _get_secret(key: str) -> Optional[str]:
    """Gets a secret from environment variables or Streamlit secrets.
    
    Checks in order:
    1. Environment variables (for local development with .env)
    2. Streamlit secrets (for Streamlit Cloud deployment)
    """
    # First check environment variables
    value = os.getenv(key)
    if value:
        return value
    
    # Then check Streamlit secrets (for cloud deployment)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    
    return None


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
    elif provider == 'azure':
        return _create_azure_client(model_name, temperature)
    else:
        raise LLMConfigError(
            f"Unsupported LLM provider: '{provider}'. "
            "Supported providers: 'google', 'openai', 'anthropic', 'azure'."
        )


def _create_google_client(model_name: str, temperature: Optional[float]) -> BaseChatModel:
    """Creates a Google Gemini LLM client."""
    _require_secret('GOOGLE_API_KEY', 'Google Gemini')

    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, Any] = {'model': model_name}
    if temperature is not None:
        kwargs['temperature'] = temperature

    return ChatGoogleGenerativeAI(**kwargs)


def _create_azure_client(model_name: str, temperature: Optional[float]) -> BaseChatModel:
    """Creates an Azure OpenAI LLM client."""
    _require_secret('AZURE_API_KEY', 'Azure OpenAI')
    _require_secret('AZURE_ENDPOINT', 'Azure OpenAI')

    from langchain_openai import AzureChatOpenAI

    kwargs: dict[str, Any] = {
        'api_key': _get_secret('AZURE_API_KEY'),
        'azure_endpoint': _get_secret('AZURE_ENDPOINT'),
        'azure_deployment': _get_secret('AZURE_DEPLOYMENT') or model_name,
        'api_version': _get_secret('API_VERSION'),
    }
    # Do not add temperature for Azure if the model does not support it.
    # if temperature is not None:
    #     kwargs['temperature'] = temperature

    return AzureChatOpenAI(**kwargs)


def _create_openai_client(model_name: str, temperature: Optional[float]) -> BaseChatModel:
    """Creates an OpenAI LLM client."""
    _require_secret('OPENAI_API_KEY', 'OpenAI')

    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {'model': model_name}
    if temperature is not None:
        kwargs['temperature'] = temperature

    return ChatOpenAI(**kwargs)


def _create_anthropic_client(model_name: str, temperature: Optional[float]) -> BaseChatModel:
    """Creates an Anthropic Claude LLM client."""
    _require_secret('ANTHROPIC_API_KEY', 'Anthropic')

    from langchain_anthropic import ChatAnthropic

    kwargs: dict[str, Any] = {'model': model_name}
    if temperature is not None:
        kwargs['temperature'] = temperature

    return ChatAnthropic(**kwargs)


def _require_secret(var_name: str, provider_name: str) -> None:
    """Checks that a required secret is available (env var or Streamlit secrets).

    Args:
        var_name: The name of the secret/environment variable.
        provider_name: The name of the provider (for error messages).

    Raises:
        LLMConfigError: If the secret is not set.
    """
    if not _get_secret(var_name):
        raise LLMConfigError(
            f"{var_name} not set. "
            f"Please set it in .env (local) or Streamlit secrets (cloud) to use {provider_name}."
        )
