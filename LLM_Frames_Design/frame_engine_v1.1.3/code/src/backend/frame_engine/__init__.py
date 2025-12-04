"""Rodin Frame Engine - A modular AI orchestration framework.

This package provides the core components for building composable AI systems
using the Frame pattern.

Note: Frame-specific data models (shared context keys, enums) are exported
from backend.frames, not from this package. Import them from the specific
frame modules or from backend.frames.
"""
from backend.frame_engine.core import (
    Frame,
    FrameContext,
    PromptSection,
    SessionLogger,
    ValidationAction,
    ValidationResult,
)
from backend.frame_engine.engine import FrameEngine
from backend.frame_engine.llm import LLMConfigError, get_llm_client

__all__ = [
    'Frame',
    'FrameContext',
    'FrameEngine',
    'LLMConfigError',
    'PromptSection',
    'SessionLogger',
    'ValidationAction',
    'ValidationResult',
    'get_llm_client',
]

