"""Tests for the PhasesCheckerFrame."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage

# Add src to path to allow imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from backend.frame_engine.core import FrameContext, ValidationAction
from backend.frames.phases_checker import PhasesCheckerFrame
from backend.frames.marty import SESSION_PHASE_KEY


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Creates a mock LLM client for predictable testing."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock()
    return mock


@pytest.fixture
def phases_checker_frame(mock_llm_client: MagicMock) -> PhasesCheckerFrame:
    """Creates a PhasesCheckerFrame instance."""
    return PhasesCheckerFrame(llm_client=mock_llm_client)


@pytest.fixture
def frame_context() -> FrameContext:
    """Creates a default FrameContext for testing."""
    return FrameContext(
        user_input="Let's make a story.",
        conversation_history=[],
        frame_memory={},
        shared_context={
            SESSION_PHASE_KEY: 1
        },
        prompt_sections=[],
        system_prompt="",
        llm_draft_response="Great idea! What should our story be about?",
        validation_results={},
        repair_attempts=0,
    )


@pytest.mark.asyncio
async def test_validate_output_passes_with_compliant_response(
    phases_checker_frame: PhasesCheckerFrame,
    mock_llm_client: MagicMock,
    frame_context: FrameContext,
):
    """
    Tests that the frame returns PASS when the LLM confirms the response
    is compliant with the phase goal.
    """
    # Arrange
    mock_llm_client.ainvoke.return_value = AIMessage(content="true")

    # Act
    result = await phases_checker_frame.validate_output(frame_context)

    # Assert
    assert result['action'] == ValidationAction.PASS
    assert result['feedback'] is None
    mock_llm_client.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_validate_output_revises_with_non_compliant_response(
    phases_checker_frame: PhasesCheckerFrame,
    mock_llm_client: MagicMock,
    frame_context: FrameContext,
):
    """
    Tests that the frame returns REVISE when the LLM flags the response
    as not compliant with the phase goal.
    """
    # Arrange
    mock_llm_client.ainvoke.return_value = AIMessage(content="false")
    frame_context['llm_draft_response'] = "Let's talk about something else."

    # Act
    result = await phases_checker_frame.validate_output(frame_context)

    # Assert
    assert result['action'] == ValidationAction.REVISE
    assert result['feedback'] is not None
    assert "did not adhere to the Phase Goal" in result['feedback']
    mock_llm_client.ainvoke.assert_called_once()
