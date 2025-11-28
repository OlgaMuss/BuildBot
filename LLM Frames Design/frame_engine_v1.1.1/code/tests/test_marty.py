"""Tests for the MnemonicCoCreatorFrame (Marty).

These tests verify:
- US4: Turn-taking management
- US5: Session phase transitions
- US7: Focus management

Note: US6 (Comprehension Monitoring) has been moved to test_comprehension_tracker.py
"""
import pytest

from backend.frames.marty import (
    CLEANED_MESSAGE_KEY,
    CONSECUTIVE_SAME_SPEAKER_KEY,
    SESSION_PHASE_KEY,
    SPEAKER_KEY,
    SUGGESTED_NEXT_SPEAKER_KEY,
)


class TestParticipationTracking:
    """Tests for US4: Turn-Taking Management - Participation Tracking."""

    @pytest.mark.asyncio
    async def test_participation_tracking(self, marty_frame, empty_context):
        """Verifies that contribution count and speaking time are tracked.

        US4: Contribution count is tracked per student.
        US4: Speaking time is estimated from message length.
        """
        context = empty_context
        context['user_input'] = 'Red: I think microcontrollers are like tiny computers!'

        # First turn
        analysis = await marty_frame.analyze_input(context)

        assert analysis is not None
        assert analysis['speaker'] == 'Red'
        assert 'participation' in analysis

        # Check Red's participation was updated
        red_participation = analysis['participation']['Red']
        assert red_participation['contribution_count'] == 1
        assert red_participation['total_speaking_time_seconds'] > 0

        # Green and Blue should still have 0 contributions
        assert analysis['participation']['Green']['contribution_count'] == 0
        assert analysis['participation']['Blue']['contribution_count'] == 0

    @pytest.mark.asyncio
    async def test_turn_taking_suggestion(self, marty_frame, empty_context):
        """Verifies that the system suggests the next speaker for fairness.

        US4: Next speaker is suggested based on fairness criteria.
        """
        context = empty_context
        frame_memory = context['frame_memory']

        # Simulate Red speaking twice
        context['user_input'] = 'Red: First message'
        await marty_frame.analyze_input(context)

        context['user_input'] = 'Red: Second message'
        analysis = await marty_frame.analyze_input(context)

        # System should suggest someone other than Red
        suggested = analysis.get('suggested_next_speaker')
        assert suggested is not None
        assert suggested != 'Red'
        assert suggested in ['Green', 'Blue']

    @pytest.mark.asyncio
    async def test_monopolization_detection(self, marty_frame, empty_context):
        """Verifies that consecutive same-speaker turns are detected.

        US4: Monopolization (3+ consecutive turns) triggers a warning.
        """
        context = empty_context

        # Simulate Red speaking three times in a row
        for i in range(3):
            context['user_input'] = f'Red: Message number {i + 1}'
            analysis = await marty_frame.analyze_input(context)

        # Should detect monopolization
        consecutive = analysis.get('consecutive_same_speaker', 0)
        assert consecutive >= 3

        # Simulate what the engine does: store analysis in shared_context[frame.name]
        context['shared_context'][marty_frame.name] = analysis

        # Prompt sections should include turn management
        sections = await marty_frame.get_prompt_sections(context)
        section_labels = [s['label'] for s in sections]
        assert 'Marty - Turn Management' in section_labels

    @pytest.mark.asyncio
    async def test_underparticipation_detection(self, marty_frame, empty_context):
        """Verifies that underparticipating students are identified.

        US4: Students with 2+ fewer contributions are flagged.
        """
        context = empty_context

        # Simulate Red speaking 4 times, Green never
        for i in range(4):
            context['user_input'] = f'Red: Message {i + 1}'
            analysis = await marty_frame.analyze_input(context)

        # Green and Blue should be flagged as underparticipating
        underparticipating = analysis.get('underparticipating_students', [])
        assert 'Green' in underparticipating or 'Blue' in underparticipating


class TestPhaseTransitions:
    """Tests for US5: Session Phase Transitions."""

    @pytest.mark.asyncio
    async def test_phase_transitions(self, marty_frame, empty_context):
        """Verifies that session progresses through phases based on turn count.

        US5: Phase transitions at configured boundaries.
        """
        context = empty_context

        # Phase 1: Turns 1-5
        for i in range(5):
            context['user_input'] = f'Red: Turn {i + 1}'
            analysis = await marty_frame.analyze_input(context)

        assert analysis['session_phase'] == 1

        # Phase 2: Turn 6
        context['user_input'] = 'Green: Turn 6'
        analysis = await marty_frame.analyze_input(context)
        assert analysis['session_phase'] == 2

        # Simulate to turn 21 for Phase 3
        for i in range(7, 21):
            context['user_input'] = f'Blue: Turn {i}'
            analysis = await marty_frame.analyze_input(context)

        assert analysis['session_phase'] == 2

        # Turn 21: Phase 3
        context['user_input'] = 'Red: Turn 21'
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

    @pytest.mark.asyncio
    async def test_redirection_after_off_topic(self, marty_frame, empty_context):
        """Verifies that redirection is triggered after consecutive off-topic turns.

        US7: After 2+ off-topic turns, redirection instruction is added.
        """
        context = empty_context
        frame_memory = context['frame_memory']

        # Manually set off-topic duration to trigger redirection
        # (This simulates the state after 2 off-topic turns)
        marty_frame._initialize_memory(frame_memory)
        frame_memory['consecutive_off_topic_turns'] = 2

        # Mock the shared_context as if analyze_input ran
        context['shared_context'][marty_frame.name] = {
            'session_phase': 2,
            'underparticipating_students': [],
            'suggested_next_speaker': None,
            'consecutive_same_speaker': 0,
            'off_topic_duration': 2,
        }

        sections = await marty_frame.get_prompt_sections(context)

        # Should include redirection section
        section_labels = [s['label'] for s in sections]
        assert 'Marty - Redirection' in section_labels

        # Redirection content should mention getting back on topic
        redirection_section = next(s for s in sections if s['label'] == 'Marty - Redirection')
        assert 'off-topic' in redirection_section['content'].lower()


class TestSharedContextKeys:
    """Tests for Marty's shared context population."""

    @pytest.mark.asyncio
    async def test_shared_context_keys_populated(self, marty_frame, empty_context):
        """Verifies that all well-known keys are populated in shared_context.

        This ensures other frames can access Marty's analysis without coupling.
        """
        context = empty_context
        context['user_input'] = 'Green: What is RAM used for in a microcontroller?'

        await marty_frame.analyze_input(context)

        shared = context['shared_context']

        # All well-known keys should be present
        assert CLEANED_MESSAGE_KEY in shared
        assert SPEAKER_KEY in shared
        assert SESSION_PHASE_KEY in shared
        assert SUGGESTED_NEXT_SPEAKER_KEY in shared
        assert CONSECUTIVE_SAME_SPEAKER_KEY in shared

        # Values should be correct types
        assert isinstance(shared[CLEANED_MESSAGE_KEY], str)
        assert shared[SPEAKER_KEY] == 'Green'
        assert isinstance(shared[SESSION_PHASE_KEY], int)
        assert isinstance(shared[CONSECUTIVE_SAME_SPEAKER_KEY], int)

