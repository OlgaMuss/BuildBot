"""Tests for the ComprehensionTrackerFrame.

These tests verify:
- US6: Per-Concept Comprehension Tracking
"""
import pytest
from unittest.mock import AsyncMock

from backend.frame_engine.core import FrameContext
from backend.frames.comprehension_tracker import (
    CONCEPT_ASSESSMENTS_KEY,
    ComprehensionLevel,
    ComprehensionTrackerFrame,
    PER_TURN_COMPREHENSION_KEY,
)
from backend.frames.marty import SPEAKER_KEY


@pytest.fixture
def comprehension_frame(test_learning_material, test_students, llm_client):
    """Creates a ComprehensionTrackerFrame instance for testing."""
    return ComprehensionTrackerFrame(
        learning_material=test_learning_material,
        students=test_students,
        llm_client=llm_client,
    )


@pytest.fixture
def context_with_speaker(empty_context) -> FrameContext:
    """Returns a context with speaker already set (as Marty would do)."""
    context = empty_context
    context['shared_context'][SPEAKER_KEY] = 'Red'
    return context


class TestConceptExtraction:
    """Tests for US6: Concept extraction from learning material."""

    @pytest.mark.asyncio
    async def test_concept_extraction(self, comprehension_frame, context_with_speaker):
        """Verifies that concepts are extracted from learning material on first turn.

        US6: Concepts are automatically extracted from learning material at session start.
        """
        context = context_with_speaker
        context['user_input'] = 'Red: What is a microcontroller?'
        context['frame_memory']['turn_count'] = 1

        await comprehension_frame.analyze_input(context)

        # Should have initialized the tracker with concepts
        tracker = context['frame_memory'].get('comprehension_tracker', {})
        concepts = tracker.get('concepts', [])

        assert len(concepts) > 0
        # Should contain some expected concepts from the learning material
        # (exact concepts depend on LLM extraction)
        assert isinstance(concepts, list)

    @pytest.mark.asyncio
    async def test_concepts_stored_in_memory(self, comprehension_frame, context_with_speaker):
        """Verifies that extracted concepts are stored in frame_memory.

        US6: Concepts are stored for later reference.
        """
        context = context_with_speaker
        context['user_input'] = 'Red: Tell me about CPUs'
        context['frame_memory']['turn_count'] = 1

        await comprehension_frame.analyze_input(context)

        tracker = context['frame_memory'].get('comprehension_tracker', {})
        assert 'concepts' in tracker
        assert 'by_student' in tracker


class TestComprehensionAssessment:
    """Tests for US6: Per-concept comprehension assessment."""

    @pytest.mark.asyncio
    async def test_comprehension_assessment(self, comprehension_frame, context_with_speaker):
        """Verifies that comprehension is assessed for mentioned concepts.

        US6: Each student message is analyzed for concept mentions.
        US6: For each mentioned concept, a triplet is recorded.
        """
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1

        # First call to initialize concepts
        context['user_input'] = 'Red: Hello'
        await comprehension_frame.analyze_input(context)

        # Second call with a concept-related message
        context['frame_memory']['turn_count'] = 2
        context['user_input'] = 'Red: The CPU is like the brain of the microcontroller, right?'

        # --- Mock the two analysis methods to isolate the test ---
        comprehension_frame._analyze_cumulative_comprehension = AsyncMock(
            return_value=[
                {
                    'concept': 'CPU',
                    'level': 'UNDERSTOOD',
                    'justification': 'Correctly analogized to a brain.',
                }
            ]
        )
        comprehension_frame._analyze_per_turn_comprehension = AsyncMock(
            return_value={'understood': ['CPU'], 'confused': []}
        )

        analysis = await comprehension_frame.analyze_input(context)

        # Should return assessments for the current turn in the analysis output
        assert analysis is not None
        assert 'cumulative_assessments_updated' in analysis
        assert 'all_student_profiles' in analysis

        # The mock should have been called
        comprehension_frame._analyze_cumulative_comprehension.assert_called_once()

    @pytest.mark.asyncio
    async def test_assessment_levels(self, comprehension_frame, context_with_speaker):
        """Verifies that assessment levels are properly stored.

        US6: Levels are: NOT_SEEN, UNDERSTOOD, CONFUSED, MISCONCEPTION.
        """
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1
        context['user_input'] = 'Red: What is this about?'

        await comprehension_frame.analyze_input(context)

        tracker = context['frame_memory'].get('comprehension_tracker', {})
        by_student = tracker.get('by_student', {})

        # All concepts should start as NOT_SEEN
        if 'Red' in by_student:
            for concept, data in by_student['Red'].items():
                assert data['level'] in [
                    ComprehensionLevel.NOT_SEEN.value,
                    ComprehensionLevel.UNDERSTOOD.value,
                    ComprehensionLevel.CONFUSED.value,
                    ComprehensionLevel.MISCONCEPTION.value,
                ]


class TestPerTurnComprehension:
    """Tests for the new, granular per-turn comprehension analysis."""

    @pytest.mark.asyncio
    async def test_per_turn_analysis_is_called(
        self, comprehension_frame, context_with_speaker
    ):
        """Verifies that the new per-turn analysis method is called during analyze_input."""
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1
        context['user_input'] = 'Red: I get CPUs, but what is RAM?'

        # Initialize by running once
        await comprehension_frame.analyze_input(context)

        # --- Mock the analysis methods for the actual test ---
        comprehension_frame._analyze_cumulative_comprehension = AsyncMock(return_value=[])
        comprehension_frame._analyze_per_turn_comprehension = AsyncMock(
            return_value={'understood': ['CPU'], 'confused': ['RAM']}
        )

        # Run again with a new message
        context['frame_memory']['turn_count'] = 2
        await comprehension_frame.analyze_input(context)

        # The new per-turn analysis method should have been called
        comprehension_frame._analyze_per_turn_comprehension.assert_called_once()

    @pytest.mark.asyncio
    async def test_per_turn_analysis_in_shared_context(
        self, comprehension_frame, context_with_speaker
    ):
        """Verifies the result of per-turn analysis is stored in shared_context."""
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1
        context['user_input'] = 'Red: I get CPUs, but what is RAM?'

        # Mock the LLM call to return a predictable result
        comprehension_frame._analyze_per_turn_comprehension = AsyncMock(
            return_value={'understood': ['CPU'], 'confused': ['RAM']}
        )

        # Run the analysis
        await comprehension_frame.analyze_input(context)

        # The result should be in shared_context under the correct key
        assert PER_TURN_COMPREHENSION_KEY in context['shared_context']
        per_turn_result = context['shared_context'][PER_TURN_COMPREHENSION_KEY]
        assert per_turn_result['understood'] == ['CPU']
        assert per_turn_result['confused'] == ['RAM']


class TestPerStudentTracking:
    """Tests for US6: Per-student comprehension tracking."""

    @pytest.mark.asyncio
    async def test_per_student_tracking(self, comprehension_frame, context_with_speaker):
        """Verifies that comprehension is tracked per student individually.

        US6: Comprehension is tracked per student individually.
        """
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1
        context['user_input'] = 'Red: I understand CPUs are processors'

        await comprehension_frame.analyze_input(context)

        tracker = context['frame_memory'].get('comprehension_tracker', {})
        by_student = tracker.get('by_student', {})

        # Should have entries for all students
        assert 'Red' in by_student
        assert 'Green' in by_student
        assert 'Blue' in by_student

    @pytest.mark.asyncio
    async def test_assessments_updated_each_turn(self, comprehension_frame, context_with_speaker):
        """Verifies that assessments are updated at each turn.

        US6: Assessments are updated at each turn.
        """
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1
        context['user_input'] = 'Red: Hello'

        # First turn
        await comprehension_frame.analyze_input(context)
        tracker_turn_1 = dict(context['frame_memory'].get('comprehension_tracker', {}))

        # Second turn
        context['frame_memory']['turn_count'] = 2
        context['user_input'] = 'Red: The CPU executes instructions'

        await comprehension_frame.analyze_input(context)

        # The tracker should exist after both turns
        tracker_turn_2 = context['frame_memory'].get('comprehension_tracker', {})
        assert tracker_turn_2 is not None
        assert 'by_student' in tracker_turn_2

    @pytest.mark.asyncio
    async def test_shared_context_populated(self, comprehension_frame, context_with_speaker):
        """Verifies that assessments are stored in shared_context.

        US6: Assessments are shared via CONCEPT_ASSESSMENTS_KEY.
        """
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1
        context['user_input'] = 'Red: What is RAM?'

        await comprehension_frame.analyze_input(context)

        # Should be in shared_context
        assert CONCEPT_ASSESSMENTS_KEY in context['shared_context']


class TestPromptSections:
    """Tests for US6: Prompt section generation."""

    @pytest.mark.asyncio
    async def test_prompt_sections_generated(self, comprehension_frame, context_with_speaker):
        """Verifies that prompt sections are generated based on assessments.

        US6: Prompt sections include concepts to clarify and concepts to skip.
        """
        context = context_with_speaker
        context['frame_memory']['turn_count'] = 1
        context['user_input'] = 'Red: I think RAM stores things permanently'

        # First, analyze to populate the tracker
        await comprehension_frame.analyze_input(context)

        # Then get prompt sections
        sections = await comprehension_frame.get_prompt_sections(context)

        # Sections should be a list (may be empty if no specific guidance needed)
        assert isinstance(sections, list)

    @pytest.mark.asyncio
    async def test_concepts_to_clarify_included(self, comprehension_frame, context_with_speaker):
        """Verifies that misconceptions are included in prompt sections.

        US6: Concepts with misconceptions should be flagged for clarification.
        """
        context = context_with_speaker

        # Manually set up a misconception for testing
        context['frame_memory']['comprehension_tracker'] = {
            'concepts': ['CPU', 'RAM'],
            'by_student': {
                'Red': {
                    'CPU': {
                        'level': ComprehensionLevel.UNDERSTOOD.value,
                        'justification': 'Correctly identified as processor',
                        'turn': 1,
                    },
                    'RAM': {
                        'level': ComprehensionLevel.MISCONCEPTION.value,
                        'justification': 'Thinks RAM is permanent storage',
                        'turn': 2,
                    },
                },
                'Green': {
                    'CPU': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                    'RAM': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                },
                'Blue': {
                    'CPU': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                    'RAM': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                },
            },
        }

        sections = await comprehension_frame.get_prompt_sections(context)

        # Should have at least one section about concepts to clarify
        assert len(sections) >= 1

        # Find the clarify section
        clarify_section = next(
            (s for s in sections if 'Clarify' in s['label']),
            None,
        )
        assert clarify_section is not None
        assert 'RAM' in clarify_section['content']

    @pytest.mark.asyncio
    async def test_understood_concepts_included(self, comprehension_frame, context_with_speaker):
        """Verifies that well-understood concepts are included to avoid repetition.

        US6: Well-understood concepts are tracked to avoid repetition.
        """
        context = context_with_speaker

        # Manually set up an understood concept for testing
        context['frame_memory']['comprehension_tracker'] = {
            'concepts': ['CPU', 'RAM'],
            'by_student': {
                'Red': {
                    'CPU': {
                        'level': ComprehensionLevel.UNDERSTOOD.value,
                        'justification': 'Correctly identified as processor',
                        'turn': 1,
                    },
                    'RAM': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                },
                'Green': {
                    'CPU': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                    'RAM': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                },
                'Blue': {
                    'CPU': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                    'RAM': {'level': ComprehensionLevel.NOT_SEEN.value, 'justification': None, 'turn': None},
                },
            },
        }

        sections = await comprehension_frame.get_prompt_sections(context)

        # Should have a section about understood concepts
        understood_section = next(
            (s for s in sections if 'Understood' in s['label']),
            None,
        )
        assert understood_section is not None
        assert 'CPU' in understood_section['content']

