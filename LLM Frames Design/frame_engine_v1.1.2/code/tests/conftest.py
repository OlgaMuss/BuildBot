"""Pytest configuration and shared fixtures for the Frame Engine tests.

To run tests:
    cd code/
    poetry run python -m pytest tests/ -v

Make sure to create tests/.env with your API key:
    GOOGLE_API_KEY="your-key-here"
"""
import os
import sys
from pathlib import Path
from typing import Any

# --- Path Setup ---
# Add the 'src' directory to the Python path to allow for absolute imports
# of the backend modules (e.g., `from backend.frame_engine.core import ...`)
# This is a standard practice for making test suites runnable from the command line.
project_root = Path(__file__).parent.parent
src_path = project_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


import pytest
import yaml
from langchain_core.messages import AIMessage

from backend.frame_engine.core import (  # noqa: E402
    Frame,
    FrameContext,
    PromptSection,
    ValidationResult,
    ValidationAction,
)
from backend.frame_engine.llm import get_llm_client  # noqa: E402
from backend.frames.comprehension_tracker import ComprehensionTrackerFrame
from backend.frames.marty import MnemonicCoCreatorFrame  # noqa: E402

# --- Constants ---
# Define a constant for the root of the project to make pathing easier.
PROJECT_ROOT = Path(__file__).parent.parent.parent


# --- Helper Functions ---

def _load_dotenv() -> None:
    """Loads the .env file from the correct location (`scripts` directory)."""
    try:
        from dotenv import load_dotenv

        # Path to the .env file in the `scripts` directory
        dotenv_path = PROJECT_ROOT / 'code' / 'scripts' / '.env'
        if dotenv_path.is_file():
            load_dotenv(dotenv_path=dotenv_path)
        else:
            # Provide a helpful message if the .env file is missing
            print(f"\nNote: .env file not found at {dotenv_path}. "
                  "Tests requiring API keys may fail.")

    except ImportError:
        # Warn if python-dotenv is not installed
        print("\nWarning: `python-dotenv` is not installed. "
              "Cannot load environment variables from .env file.")


# --- Fixture Configuration ---

# Load environment variables at the start of the test session
_load_dotenv()


def load_test_config() -> dict:
    """Loads the test configuration from tests/config.yaml."""
    config_path = Path(__file__).parent / 'config.yaml'
    with config_path.open('r') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope='session')
def test_config() -> dict:
    """Provides the test configuration as a session-scoped fixture."""
    return load_test_config()


@pytest.fixture(scope='session')
def test_learning_material(test_config) -> str:
    """Provides the test learning material from the config."""
    return test_config.get('test', {}).get('learning_material', 'Default learning material.')


@pytest.fixture(scope='session')
def test_students(test_config) -> list[str]:
    """Provides the list of test students from the config."""
    return test_config.get('test', {}).get('students', ['Red', 'Green', 'Blue'])


@pytest.fixture(scope='session')
def llm_client(test_config):
    """Provides an LLM client for testing, configured via config."""
    # Ensure the environment is loaded, which conftest does automatically
    # by finding the .env file.
    provider = test_config.get('llm', {}).get('provider', 'azure')
    model_name = test_config.get('llm', {}).get(provider, {}).get('model_name', 'gpt-4.1-mini')

    try:
        return get_llm_client(
            provider=provider,
            model_name=model_name,
            temperature=0.0,
        )
    except Exception as e:
        pytest.fail(
            f"Failed to initialize {provider.capitalize()} LLM client: {e}. "
            f"Ensure your API key is set in a .env file in the 'scripts' directory."
        )


@pytest.fixture
def marty_frame(test_config, llm_client) -> MnemonicCoCreatorFrame:
    """Creates a MnemonicCoCreatorFrame instance for testing."""
    return MnemonicCoCreatorFrame(
        topic=test_config.get('test', {}).get('topic', 'Microcontrollers'),
        learning_material=test_config.get('test', {}).get('learning_material', 'Test material.'),
        students=test_config.get('test', {}).get('students', ['Red', 'Green', 'Blue']),
        mnemonic_type='Story',
        phase_config=test_config.get('phases', {'phase_1_end': 5, 'phase_2_end': 20}),
        llm_client=llm_client,
        target_age=14,  # Add a default age for consistency in tests
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
