"""Tests for the LanguageCheckerFrame."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage

# Add src to path to allow imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from backend.frame_engine.core import FrameContext, ValidationAction
from backend.frames.language_checker import LanguageCheckerFrame


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Creates a mock LLM client for predictable testing."""
    mock = MagicMock()
    # Configure the mock's async behavior correctly for await calls
    mock.ainvoke = AsyncMock()
    return mock


@pytest.fixture
def language_checker_frame(mock_llm_client: MagicMock) -> LanguageCheckerFrame:
    """Creates a LanguageCheckerFrame instance with a target age of 10."""
    return LanguageCheckerFrame(
        target_age=10,
        llm_client=mock_llm_client,
        learning_material="Microcontrollers use ESP32 modules and pins.",
    )


@pytest.fixture
def frame_context() -> FrameContext:
    """Creates a default FrameContext for testing."""
    return FrameContext(
        user_input="Tell me a story.",
        conversation_history=[],
        frame_memory={},
        shared_context={},
        prompt_sections=[],
        system_prompt="",
        llm_draft_response="This is a simple story for kids.",
        validation_results={},
        repair_attempts=0,
    )


@pytest.mark.asyncio
async def test_validate_output_passes_with_appropriate_language(
    language_checker_frame: LanguageCheckerFrame,
    mock_llm_client: MagicMock,
    frame_context: FrameContext,
):
    """
    Tests that the frame returns PASS when the LLM confirms the language is
    age-appropriate.
    """
    # Arrange: Mock the LLM to return "true"
    mock_llm_client.ainvoke.return_value = AIMessage(content="true")

    # Act: Run the validation
    result = await language_checker_frame.validate_output(frame_context)

    # Assert: Check that the result is PASS
    assert result['action'] == ValidationAction.PASS
    assert result['feedback'] is None
    mock_llm_client.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_validate_output_revises_with_inappropriate_language(
    language_checker_frame: LanguageCheckerFrame,
    mock_llm_client: MagicMock,
    frame_context: FrameContext,
):
    """
    Tests that the frame returns REVISE when the LLM flags the language as
    not age-appropriate.
    """
    # Arrange: Mock the LLM to return "false"
    mock_llm_client.ainvoke.return_value = AIMessage(content="false")
    frame_context['llm_draft_response'] = "This response contains overly complex and sesquipedalian vocabulary."

    # Act: Run the validation
    result = await language_checker_frame.validate_output(frame_context)

    # Assert: Check that the result is REVISE and contains feedback
    assert result['action'] == ValidationAction.REVISE
    assert result['feedback'] is not None
    assert "not appropriate for a 10-year-old" in result['feedback']
    mock_llm_client.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_validate_output_handles_unexpected_llm_response(
    language_checker_frame: LanguageCheckerFrame,
    mock_llm_client: MagicMock,
    frame_context: FrameContext,
):
    """
    Tests that the frame defaults to PASS if the LLM response is not "false".
    This is a safeguard against unexpected LLM outputs.
    """
    # Arrange: Mock the LLM to return an unexpected string
    mock_llm_client.ainvoke.return_value = AIMessage(content="I am not sure.")

    # Act: Run the validation
    result = await language_checker_frame.validate_output(frame_context)

    # Assert: The result should be PASS
    assert result['action'] == ValidationAction.PASS
    mock_llm_client.ainvoke.assert_called_once()
