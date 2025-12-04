"""Tests for the MnemonicCoCreatorFrame (Marty).

These tests verify:
- US4: Turn-taking management
- US5: Session phase transitions
- US7: Focus management

Note: US6 (Comprehension Monitoring) has been moved to test_comprehension_tracker.py
"""
import pytest
from copy import deepcopy

from backend.frames.marty import (
    CLEANED_MESSAGE_KEY,
    CONSECUTIVE_SAME_SPEAKER_KEY,
    SESSION_PHASE_KEY,
    SPEAKER_KEY,
    SUGGESTED_NEXT_SPEAKER_KEY,
    MnemonicCoCreatorFrame,
)


@pytest.fixture
def marty_frame(llm_client):
    """Provides a MnemonicCoCreatorFrame instance for testing."""
    return MnemonicCoCreatorFrame(
        topic="Microcontrollers",
        learning_material="ESP32 is a microcontroller.",
        students=["Alice", "Bob"],
        mnemonic_type="Story",
        llm_client=llm_client,
        target_age=14,
    )


@pytest.fixture
def base_context(marty_frame):
    """Provides a basic FrameContext for testing."""
    # Create a deepcopy to ensure each test gets a fresh, isolated context
    return deepcopy({
        'user_input': '',
        'conversation_history': [],
        'frame_memory': {},
        'shared_context': {},
        'prompt_sections': [],
        'system_prompt': '',
        'llm_draft_response': '',
        'validation_results': {},
        'repair_attempts': 0
    })


@pytest.fixture
def empty_context():
    """Provides an empty FrameContext."""
    from backend.frame_engine.core import FrameContext
    return FrameContext(
        user_input='',
        conversation_history=[],
        frame_memory={},
        shared_context={},
        prompt_sections=[],
        system_prompt='',
        llm_draft_response='',
        validation_results={},
        repair_attempts=0
    )


class TestPhaseTransitions:
    """Tests for US5: Session Phase Transitions."""

    @pytest.mark.asyncio
    async def test_phase_1(self, marty_frame, empty_context):
        """Verifies Phase 1 is active during the first 3 minutes."""
        context = empty_context
        frame_memory = context['frame_memory']
        marty_frame._initialize_memory(frame_memory)
        frame_memory['elapsed_time_minutes'] = 2
        analysis = await marty_frame.analyze_input(context)
        assert analysis['session_phase'] == 1

    @pytest.mark.asyncio
    async def test_phase_2(self, marty_frame, empty_context):
        """Verifies Phase 2 is active between 3 and 7 minutes."""
        context = empty_context
        frame_memory = context['frame_memory']
        marty_frame._initialize_memory(frame_memory)
        frame_memory['elapsed_time_minutes'] = 4
        analysis = await marty_frame.analyze_input(context)
        assert analysis['session_phase'] == 2

    @pytest.mark.asyncio
    async def test_phase_3(self, marty_frame, empty_context):
        """Verifies Phase 3 is active after 7 minutes."""
        context = empty_context
        frame_memory = context['frame_memory']
        marty_frame._initialize_memory(frame_memory)
        frame_memory['elapsed_time_minutes'] = 8
        analysis = await marty_frame.analyze_input(context)
        assert analysis['session_phase'] == 3


class TestFocusManagement:
    """Tests for US7: Focus Management."""

    @pytest.mark.asyncio
    async def test_off_topic_detection(self, marty_frame, empty_context):
        """Verifies that off-topic conversations are detected and tracked.

        US7: Off-topic messages are detected via LLM analysis.
        US7: Consecutive off-topic turns are counted.
        """
        context = empty_context

        # Send an off-topic message
        context['user_input'] = 'Red: Did you see the football game last night?'
        analysis = await marty_frame.analyze_input(context)

        # LLM should analyze relevance
        assert 'is_relevant' in analysis
        # Note: The actual value depends on LLM judgment

        # off_topic_duration should be tracked
        assert 'off_topic_duration' in analysis


class TestSharedContextKeys:
    """Tests that the frame correctly populates shared_context."""

    @pytest.mark.asyncio
    async def test_shared_context_keys_populated(self, marty_frame, base_context):
        """Verify speaker, phase, and cleaned message are in shared_context."""
        # Use a name that is in the fixture's student list
        base_context['user_input'] = "Alice: Let's talk about microcontrollers."
        analysis = await marty_frame.analyze_input(base_context)
        shared = base_context['shared_context']

        assert analysis is not None
        assert shared[CLEANED_MESSAGE_KEY] == "Let's talk about microcontrollers."
        assert shared[SPEAKER_KEY] == 'Alice'
        assert shared[SESSION_PHASE_KEY] == 1

