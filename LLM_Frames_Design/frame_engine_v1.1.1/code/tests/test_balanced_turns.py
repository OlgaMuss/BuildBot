"""Tests for the BalancedTurnsFrame.

This test suite verifies that the BalancedTurnsFrame correctly validates
turn-taking to maintain balanced student participation.
"""
import pytest

from backend.frame_engine.core import FrameContext, ValidationAction
from backend.frames.balanced_turns import BalancedTurnsFrame
from backend.frames.marty import SUGGESTED_NEXT_SPEAKER_KEY


@pytest.fixture
def students():
    """Standard list of student names for testing."""
    return ['Red', 'Blue', 'Green']


@pytest.fixture
def balanced_turns_frame(students):
    """Create a BalancedTurnsFrame instance for testing."""
    return BalancedTurnsFrame(students=students)


@pytest.fixture
def context_with_suggestion(students):
    """Create a FrameContext with turn-taking suggestion."""
    return FrameContext(
        user_input="Red: This is interesting!",
        conversation_history=[],
        frame_memory={},
        shared_context={
            'mnemonic_co_creator_marty': {
                'speaker': 'Red',
                'turn_count': 5,
            },
            SUGGESTED_NEXT_SPEAKER_KEY: 'Blue',  # Blue should be invited
        },
        prompt_sections=[],
        system_prompt='',
        llm_draft_response='',
        validation_results={},
        repair_attempts=0
    )


# --- Test: Validation Pass Cases ---

@pytest.mark.asyncio
async def test_validation_passes_when_correct_next_speaker_invited(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation passes when Marty invites the suggested next speaker."""
    # Marty correctly acknowledges Red and invites Blue
    context_with_suggestion['llm_draft_response'] = (
        "Great point, Red! That's really interesting. "
        "Blue, what are your thoughts on this?"
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.PASS
    assert result['feedback'] is None


@pytest.mark.asyncio
async def test_validation_passes_when_no_suggestion(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation passes when no next speaker is suggested."""
    # Remove the suggestion
    context_with_suggestion['shared_context'][SUGGESTED_NEXT_SPEAKER_KEY] = None
    context_with_suggestion['llm_draft_response'] = (
        "That's a great point, Red! Can you elaborate more?"
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.PASS


@pytest.mark.asyncio
async def test_validation_passes_when_suggestion_is_previous_speaker(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation passes when suggested speaker is the one who just spoke."""
    # Suggested next is same as previous (no change needed)
    context_with_suggestion['shared_context'][SUGGESTED_NEXT_SPEAKER_KEY] = 'Red'
    context_with_suggestion['llm_draft_response'] = (
        "That's interesting, Red! Tell us more about that."
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.PASS


# --- Test: Validation Fail Cases ---

@pytest.mark.asyncio
async def test_validation_fails_when_wrong_student_invited(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation fails when Marty invites the wrong student."""
    # Marty invites Green instead of Blue
    context_with_suggestion['llm_draft_response'] = (
        "Great point, Red! That's really interesting. "
        "Green, what do you think about this?"
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.REVISE
    assert 'Blue' in result['feedback']  # Should mention who to invite
    assert 'Green' in result['feedback']  # Should mention the error


@pytest.mark.asyncio
async def test_validation_fails_when_suggested_speaker_not_mentioned(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation fails when suggested speaker is not invited at all."""
    # Marty doesn't invite anyone
    context_with_suggestion['llm_draft_response'] = (
        "That's a really interesting point! Let's think about this more carefully."
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.REVISE
    assert 'Blue' in result['feedback']
    assert 'balanced participation' in result['feedback'].lower()


@pytest.mark.asyncio
async def test_validation_fails_when_students_swapped(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation fails when students are mentioned in wrong order."""
    # Marty mentions Blue first, then Red (should be Red first, then Blue)
    context_with_suggestion['llm_draft_response'] = (
        "Blue, I think that's an interesting point that Red made. "
        "Red was saying something important earlier."
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.REVISE
    assert 'FIRST acknowledge Red' in result['feedback'] or 'swapped' in result['feedback'].lower()


@pytest.mark.asyncio
async def test_validation_fails_when_next_speaker_in_first_half(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation fails when next speaker is mentioned ONLY in acknowledgment part."""
    # Blue mentioned in first half but Red not mentioned at all
    context_with_suggestion['llm_draft_response'] = (
        "Blue, I think that's really interesting! "
        "Can you tell us more about your thinking on this?"
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    # This should fail because Red was not acknowledged first
    assert result['action'] == ValidationAction.REVISE


@pytest.mark.asyncio
async def test_validation_fails_when_only_previous_speaker_mentioned(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation fails when only previous speaker is mentioned."""
    # Red mentioned but Blue (suggested next) is never mentioned
    context_with_suggestion['llm_draft_response'] = (
        "That's really interesting, Red! Can you tell us more? "
        "I'd love to hear you expand on that idea."
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    # Should fail because Blue was never invited
    assert result['action'] == ValidationAction.REVISE
    assert 'Blue' in result['feedback']


# --- Test: Edge Cases ---

@pytest.mark.asyncio
async def test_validation_handles_missing_speaker_data(balanced_turns_frame):
    """Test that validation passes gracefully when speaker data is missing."""
    context = FrameContext(
        user_input="Test message",
        conversation_history=[],
        frame_memory={},
        shared_context={},  # No Marty analysis
        prompt_sections=[],
        system_prompt='',
        llm_draft_response='Some response',
        validation_results={},
        repair_attempts=0
    )
    
    result = await balanced_turns_frame.validate_output(context)
    
    # Should pass (no data to validate)
    assert result['action'] == ValidationAction.PASS


@pytest.mark.asyncio
async def test_validation_with_multiple_wrong_students(
    balanced_turns_frame, context_with_suggestion
):
    """Test validation when multiple wrong students are mentioned."""
    # Marty mentions both Green and a non-existent student
    context_with_suggestion['llm_draft_response'] = (
        "Great, Red and Green! Now let's hear from someone else."
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.REVISE
    assert 'Green' in result['feedback']


@pytest.mark.asyncio
async def test_frame_name(balanced_turns_frame):
    """Test that the frame has the correct name."""
    assert balanced_turns_frame.name == 'balanced_turns_validator'


@pytest.mark.asyncio
async def test_validation_with_case_sensitive_names(
    balanced_turns_frame, context_with_suggestion
):
    """Test that student name matching is case-sensitive."""
    # Use lowercase "blue" (should not match "Blue")
    context_with_suggestion['llm_draft_response'] = (
        "Great point, Red! Now let's hear from blue."
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    # Should fail because "Blue" (capital B) is not found
    assert result['action'] == ValidationAction.REVISE


# --- Test: Complex Scenarios ---

@pytest.mark.asyncio
async def test_validation_with_long_response(
    balanced_turns_frame, context_with_suggestion
):
    """Test validation with a longer, more realistic response."""
    context_with_suggestion['llm_draft_response'] = (
        "That's a fantastic observation, Red! You're really getting to the heart "
        "of how microcontrollers work. The idea of thinking about pins as connection "
        "points is exactly right. Now, Blue, I'd love to hear your perspective on this. "
        "What do you think about Red's analogy? Can you build on it or suggest another "
        "way to think about pins?"
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    assert result['action'] == ValidationAction.PASS


@pytest.mark.asyncio
async def test_validation_detects_swapped_order_correctly(
    balanced_turns_frame, context_with_suggestion
):
    """Test that validation detects when students are addressed in wrong order."""
    # Blue's name appears early, Red's appears late - this is swapped
    context_with_suggestion['llm_draft_response'] = (
        "Blue, I think Red made an interesting point. "
        "Red was talking about something important."
    )
    
    result = await balanced_turns_frame.validate_output(context_with_suggestion)
    
    # Should fail - Blue should be mentioned in second half, not first
    assert result['action'] == ValidationAction.REVISE
    assert 'swapped' in result['feedback'].lower() or 'FIRST acknowledge Red' in result['feedback']

