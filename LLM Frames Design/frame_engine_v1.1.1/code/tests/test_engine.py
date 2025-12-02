"""Tests for the Frame Engine core functionality.

These tests verify:
- US1: Frame pipeline execution
- US2: Validation loop behavior
- US3: Prompt section accumulation
"""
import pytest
from unittest.mock import MagicMock

from backend.frame_engine.engine import FALLBACK_RESPONSE, FrameEngine


class TestPipelineExecution:
    """Tests for US1: Frame Pipeline Execution."""

    @pytest.mark.asyncio
    async def test_pipeline_executes_all_slots(self, pass_through_frame, llm_client):
        """Verifies that all pipeline slots execute in order.

        US1: Frame pipeline executes all slots in the correct order.
        """
        engine = FrameEngine(frames=[pass_through_frame], llm_client=llm_client)

        result = await engine.ainvoke(
            user_input='Hello, Marty!',
            conversation_history=[],
            frame_memory={},
        )

        # The pipeline should complete and return a response
        assert 'response' in result
        assert 'final_state' in result
        assert result['response'] != ''

        # The final state should contain all expected keys
        final_state = result['final_state']
        assert 'shared_context' in final_state
        assert 'system_prompt' in final_state
        assert 'llm_draft_response' in final_state
        assert 'validation_results' in final_state

    @pytest.mark.asyncio
    async def test_multiple_frames_compose(self, llm_client):
        """Verifies that multiple frames can be composed together.

        US1: Frame pipeline executes all slots in the correct order.
        """
        from conftest import PassThroughFrame

        frame_a = PassThroughFrame(name='frame_a')
        frame_b = PassThroughFrame(name='frame_b')

        engine = FrameEngine(frames=[frame_a, frame_b], llm_client=llm_client)

        result = await engine.ainvoke(
            user_input='Test input',
            conversation_history=[],
            frame_memory={},
        )

        # Both frames should have contributed to shared_context
        shared_context = result['final_state']['shared_context']
        assert 'frame_a' in shared_context
        assert 'frame_b' in shared_context


class TestValidationLoop:
    """Tests for US2: Validation Loop behavior."""

    @pytest.mark.asyncio
    async def test_validation_pass(self, pass_through_frame, llm_client):
        """Verifies that PASS validation returns the response immediately.

        US2: PASS from all frames → response is returned.
        """
        engine = FrameEngine(frames=[pass_through_frame], llm_client=llm_client)

        result = await engine.ainvoke(
            user_input='Simple question',
            conversation_history=[],
            frame_memory={},
        )

        # Should return a valid response (not the fallback)
        assert result['response'] != FALLBACK_RESPONSE
        assert result['response'] != ''

    @pytest.mark.asyncio
    async def test_validation_fail(self, failing_frame, llm_client):
        """Verifies that FAIL validation returns the fallback response.

        US2: FAIL from any frame → fallback response is returned.
        """
        engine = FrameEngine(frames=[failing_frame], llm_client=llm_client)

        result = await engine.ainvoke(
            user_input='This will fail validation',
            conversation_history=[],
            frame_memory={},
        )

        # Should return the fallback response
        assert result['response'] == FALLBACK_RESPONSE

    @pytest.mark.asyncio
    async def test_validation_revise(self, revise_frame, llm_client):
        """Verifies that REVISE triggers a regeneration with feedback.

        US2: REVISE from any frame → LLM is called again with feedback.
        """
        engine = FrameEngine(frames=[revise_frame], llm_client=llm_client)

        result = await engine.ainvoke(
            user_input='Test revise behavior',
            conversation_history=[],
            frame_memory={},
        )

        # The frame should have been called twice (initial + after revise)
        assert revise_frame._call_count >= 2

        # Should return a valid response after revision
        assert result['response'] != FALLBACK_RESPONSE


class TestPromptAccumulation:
    """Tests for US3: Prompt Section Accumulation."""

    @pytest.mark.asyncio
    async def test_prompt_accumulation(self, llm_client):
        """Verifies that prompt sections from multiple frames are accumulated.

        US3: Sections from multiple frames are joined correctly.
        """
        from conftest import PassThroughFrame

        frame_a = PassThroughFrame(name='alpha')
        frame_b = PassThroughFrame(name='beta')

        engine = FrameEngine(
            frames=[frame_a, frame_b],
            llm_client=llm_client,
            include_section_labels=False,  # No labels for cleaner prompts
        )

        result = await engine.ainvoke(
            user_input='Test accumulation',
            conversation_history=[],
            frame_memory={},
        )

        # The system prompt should contain content from both frames
        system_prompt = result['final_state']['system_prompt']
        assert 'Content from alpha' in system_prompt
        assert 'Content from beta' in system_prompt

    @pytest.mark.asyncio
    async def test_prompt_with_labels(self, llm_client):
        """Verifies that section labels are included when enabled.

        US3: Section labels are optional (controlled by include_section_labels).
        """
        from conftest import PassThroughFrame

        frame = PassThroughFrame(name='labeled_frame')

        engine = FrameEngine(
            frames=[frame],
            llm_client=llm_client,
            include_section_labels=True,
        )

        result = await engine.ainvoke(
            user_input='Test labels',
            conversation_history=[],
            frame_memory={},
        )

        # The system prompt should include the label
        system_prompt = result['final_state']['system_prompt']
        assert '[labeled_frame Section]' in system_prompt


class TestSessionLogging:
    """Tests for session logging functionality."""

    @pytest.mark.asyncio
    async def test_end_session_saves_log_with_markdown(self, llm_client):
        """Verifies that end_session calls the logger to save the report.

        This test ensures the new Markdown reporting feature is triggered.
        """
        # Create a mock SessionLogger
        mock_logger = MagicMock()
        mock_logger.save = MagicMock()

        engine = FrameEngine(
            frames=[],
            llm_client=llm_client,
            session_logger=mock_logger,
        )

        # The final state would normally be built up over a conversation
        final_state = {
            'frame_memory': {'turn_count': 5, 'some_data': 'value'},
            'conversation_history': [],
        }

        # Call the method to end the session
        await engine.end_session(final_state)

        # Verify that the logger's save method was called correctly
        mock_logger.save.assert_called_once_with(
            frame_memory=final_state['frame_memory'],
            generate_markdown_report=True,
        )
