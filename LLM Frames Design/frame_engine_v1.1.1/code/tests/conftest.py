"""Pytest configuration and shared fixtures for the Frame Engine tests.

To run tests:
    cd code/
    poetry run python -m pytest tests/ -v

Make sure to create tests/.env with your API key:
    GOOGLE_API_KEY="your-key-here"
"""
import logging
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# Add the src directory to the path so we can import the backend package
tests_dir = Path(__file__).parent
project_root = tests_dir.parent
src_path = project_root / 'src'
sys.path.insert(0, str(src_path))

from backend.frame_engine.core import (  # noqa: E402
    Frame,
    FrameContext,
    PromptSection,
    ValidationAction,
    ValidationResult,
)
from backend.frame_engine.llm import get_llm_client  # noqa: E402
from backend.frames.comprehension_tracker import ComprehensionTrackerFrame  # noqa: E402
from backend.frames.marty import MnemonicCoCreatorFrame  # noqa: E402


def _load_env() -> None:
    """Loads environment variables from .env file in tests directory."""
    try:
        from dotenv import load_dotenv
        env_path = tests_dir / '.env'
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path)
    except ImportError:
        pass  # dotenv not installed, rely on system env vars


def _load_config() -> dict[str, Any]:
    """Loads the test configuration from config.yaml."""
    config_path = tests_dir / 'config.yaml'
    with config_path.open('r') as f:
        return yaml.safe_load(f)


# Load env and config at module level
_load_env()
_config = _load_config()

# Configure logging based on config
log_level = _config.get('log_level', 'WARNING').upper()
logging.basicConfig(level=log_level, format='%(levelname)s - %(message)s')


@pytest.fixture(scope='session')
def config() -> dict[str, Any]:
    """Returns the test configuration dictionary."""
    return _config


@pytest.fixture(scope='session')
def llm_client():
    """Creates an LLM client for the test session.

    This is session-scoped to avoid creating multiple clients.
    Uses actual LLM calls (no mocking).
    """
    llm_config = _config.get('llm', {})
    return get_llm_client(
        provider=llm_config.get('provider', 'google'),
        model_name=llm_config.get('model_name', 'gemini-2.5-flash-lite'),
        temperature=llm_config.get('temperature'),
    )


@pytest.fixture
def test_topic(config) -> str:
    """Returns the test topic."""
    return config.get('test', {}).get('topic', 'Microcontrollers')


@pytest.fixture
def test_learning_material(config) -> str:
    """Returns the test learning material."""
    return config.get('test', {}).get('learning_material', 'Test material.')


@pytest.fixture
def test_students(config) -> list[str]:
    """Returns the test student names."""
    return config.get('test', {}).get('students', ['Red', 'Green', 'Blue'])


@pytest.fixture
def phase_config(config) -> dict[str, int]:
    """Returns the phase configuration for Marty."""
    return config.get('phases', {'phase_1_end': 5, 'phase_2_end': 20})


@pytest.fixture
def marty_frame(
    test_topic,
    test_learning_material,
    test_students,
    phase_config,
    llm_client,
) -> MnemonicCoCreatorFrame:
    """Creates a MnemonicCoCreatorFrame instance for testing."""
    return MnemonicCoCreatorFrame(
        topic=test_topic,
        learning_material=test_learning_material,
        students=test_students,
        mnemonic_type='Story',
        phase_config=phase_config,
        llm_client=llm_client,
    )


@pytest.fixture
def comprehension_frame(
    test_learning_material,
    test_students,
    llm_client,
) -> ComprehensionTrackerFrame:
    """Creates a ComprehensionTrackerFrame instance for testing."""
    return ComprehensionTrackerFrame(
        learning_material=test_learning_material,
        students=test_students,
        llm_client=llm_client,
    )


@pytest.fixture
def empty_frame_memory() -> dict[str, Any]:
    """Returns an empty frame memory dict for a fresh session."""
    return {}


@pytest.fixture
def empty_context(empty_frame_memory) -> FrameContext:
    """Returns a minimal FrameContext for testing."""
    return FrameContext(
        user_input='',
        conversation_history=[],
        frame_memory=empty_frame_memory,
        shared_context={},
        prompt_sections=[],
        system_prompt='',
        llm_draft_response='',
        validation_results={},
        repair_attempts=0,
    )


# --- Helper Frame for Testing ---

class PassThroughFrame(Frame):
    """A minimal frame that always passes validation. Used for testing the engine."""

    def __init__(self, name: str = 'pass_through'):
        super().__init__()
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def get_prompt_sections(self, context: FrameContext) -> list[PromptSection]:
        return [{'label': f'{self._name} Section', 'content': f'Content from {self._name}'}]


class FailingFrame(Frame):
    """A frame that always returns FAIL. Used for testing validation failure."""

    def __init__(self, name: str = 'failing_frame'):
        super().__init__()
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        return {'action': ValidationAction.FAIL, 'feedback': 'This frame always fails.'}


class ReviseFrame(Frame):
    """A frame that returns REVISE on first call, then PASS. Used for testing repair loop."""

    def __init__(self, name: str = 'revise_frame'):
        super().__init__()
        self._name = name
        self._call_count = 0

    @property
    def name(self) -> str:
        return self._name

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        self._call_count += 1
        if self._call_count == 1:
            return {'action': ValidationAction.REVISE, 'feedback': 'Please be more concise.'}
        return {'action': ValidationAction.PASS, 'feedback': None}


@pytest.fixture
def pass_through_frame() -> PassThroughFrame:
    """Returns a PassThroughFrame instance."""
    return PassThroughFrame()


@pytest.fixture
def failing_frame() -> FailingFrame:
    """Returns a FailingFrame instance."""
    return FailingFrame()


@pytest.fixture
def revise_frame() -> ReviseFrame:
    """Returns a ReviseFrame instance."""
    return ReviseFrame()
