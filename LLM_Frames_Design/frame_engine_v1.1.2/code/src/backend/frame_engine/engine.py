"""The core orchestration logic for the Rodin Frame Engine.

This module uses LangGraph to construct and execute a state machine that represents
the four-slot frame pipeline.
"""
import asyncio
import logging
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    PromptSection,
    SessionLogger,
    ValidationAction,
)
from backend.frames.comprehension_tracker import PER_TURN_COMPREHENSION_KEY

# Import from marty for the well-known shared context key
CLEANED_MESSAGE_KEY = '_cleaned_message'

# A named constant for the maximum number of times the engine will try to
# repair a faulty LLM response before giving up.
MAX_REPAIR_ATTEMPTS = 2

# A named constant for a generic, safe response to be used when the
# engine fails to generate a valid one.
FALLBACK_RESPONSE = (
    "I'm having trouble generating a helpful response right now. "
    "Let's pause and try again in a moment."
)


class FrameEngine:
    """Orchestrates the execution of the Rodin Frame pipeline using LangGraph."""

    def __init__(
        self,
        frames: list[Frame],
        llm_client: BaseChatModel,
        include_section_labels: bool = False,
        session_logger: Optional[SessionLogger] = None,
    ):
        """Initializes the FrameEngine.

        Args:
            frames: A list of instantiated Frame objects to be used in the pipeline.
            llm_client: An instantiated LangChain chat model client.
            include_section_labels: If True, adds `[Label]` markers to the prompt
                for debugging. Defaults to False for cleaner prompts.
            session_logger: Optional SessionLogger for detailed session logging.
        """
        self.frames = frames
        self.llm = llm_client
        self.include_section_labels = include_section_labels
        self.session_logger = session_logger
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Builds the LangGraph state machine for the frame pipeline."""
        builder = StateGraph(FrameContext)

        # 1. Define Nodes
        builder.add_node('analyze_input', self._analyze_input_node)
        builder.add_node('shape_prompt', self._shape_prompt_node)
        builder.add_node('generate_response', self._generate_response_node)
        builder.add_node('validate_output', self._validate_output_node)
        builder.add_node('repair_output', self._repair_output_node)

        # 2. Define Edges
        builder.set_entry_point('analyze_input')
        builder.add_edge('analyze_input', 'shape_prompt')
        builder.add_edge('shape_prompt', 'generate_response')
        builder.add_edge('generate_response', 'validate_output')

        builder.add_conditional_edges(
            'validate_output',
            self._decide_on_validation,
            {
                'repair': 'repair_output',
                'finish': END,
            },
        )

        builder.add_conditional_edges(
            'repair_output',
            self._decide_after_repair,
            {
                'regenerate': 'generate_response',
                'validate': 'validate_output',
                'fail': END
            }
        )

        return builder.compile()

    # --- Node Implementations ---

    async def _analyze_input_node(self, state: FrameContext) -> FrameContext:
        """The first node in the graph, corresponding to Slot 1.

        Runs the `analyze_input` method for each frame and populates the
        `shared_context`.
        """
        logging.info('--- SLOT 1: Analyze Input ---')
        # Use the existing shared_context from state, preserving any direct writes
        # by frames (e.g., SUGGESTED_NEXT_SPEAKER_KEY from balanced_turns).
        shared_context = state.setdefault('shared_context', {})
        for frame in self.frames:
            result = await frame.analyze_input(state)
            if result:
                shared_context[frame.name] = result
                logging.info("  - Frame '%s' analysis: %s", frame.name, result)
                if self.session_logger:
                    self.session_logger.log_slot('analyze_input', frame.name, details=result)
            else:
                shared_context[frame.name] = {}
                if self.session_logger:
                    self.session_logger.log_slot('analyze_input', frame.name, details={'result': 'no_output'})
        return state

    async def _shape_prompt_node(self, state: FrameContext) -> FrameContext:
        """The second node, corresponding to Slot 2.

        Accumulates prompt sections from all frames, then allows each frame
        to optionally transform the final prompt.
        """
        logging.info('--- SLOT 2: Shape Prompt ---')

        # Phase 2a: Accumulate prompt sections from all frames
        all_sections: list[PromptSection] = []
        for frame in self.frames:
            sections = await frame.get_prompt_sections(state)
            if sections:
                all_sections.extend(sections)
                logging.debug("  - Frame '%s' contributed %d section(s)", frame.name, len(sections))
                if self.session_logger:
                    section_labels = [s['label'] for s in sections]
                    self.session_logger.log_slot(
                        'get_prompt_sections', frame.name,
                        details={'sections': section_labels},
                    )

        state['prompt_sections'] = all_sections

        # Assemble the sections into a single prompt
        assembled_prompt = self._assemble_prompt(all_sections)
        state['system_prompt'] = assembled_prompt

        # Phase 2b: Allow frames to transform the assembled prompt
        for frame in self.frames:
            transformed = await frame.shape_prompt(state)
            if transformed != state['system_prompt']:
                logging.debug("  - Frame '%s' transformed the prompt", frame.name)
                if self.session_logger:
                    self.session_logger.log_slot('shape_prompt', frame.name, details={'transformed': True})
                state['system_prompt'] = transformed

        logging.info('  - System prompt shaped successfully.')
        logging.debug('  - Final System Prompt:\n---\n%s\n---', state['system_prompt'])
        return state

    def _assemble_prompt(self, sections: list[PromptSection]) -> str:
        """Assembles prompt sections into a single string.

        Args:
            sections: The list of `PromptSection` objects to assemble.

        Returns:
            The assembled prompt string.
        """
        if not sections:
            return ''

        parts = []
        for section in sections:
            if self.include_section_labels:
                # Add labeled section for debugging
                parts.append(f'[{section["label"]}]\n{section["content"]}')
            else:
                parts.append(section['content'])

        return '\n\n'.join(parts)

    def _parse_llm_response(self, response: Any) -> str:
        """Extracts the string content from a potentially complex LLM response object."""
        # The response might be a simple string, an AIMessage, or a more
        # complex object with a `content` attribute. This helper handles them.
        if isinstance(response, str):
            return response

        draft = getattr(response, 'content', '')
        if isinstance(draft, list):
            # Handle cases where content is a list of parts (e.g., multimodal)
            return ''.join(
                part.get('text', '')
                for part in draft
                if isinstance(part, dict)
            )
        if not draft and hasattr(response, 'text'):
            return response.text

        return draft

    async def _generate_response_node(self, state: FrameContext) -> FrameContext:
        """The third node, which calls the LLM.

        Constructs the message history and sends the request to the LLM,
        storing the output in `llm_draft_response`.
        """
        logging.info('--- SLOT 3: Generate ---')
        prompt = state['system_prompt']
        history = state['conversation_history']

        # Use the cleaned message if available, otherwise fall back to raw input.
        shared_context = state.get('shared_context', {})
        clean_message = shared_context.get(CLEANED_MESSAGE_KEY, state['user_input'])

        messages = [SystemMessage(content=prompt)]
        for turn in history:
            if turn.get('role') == 'user':
                messages.append(HumanMessage(content=turn['content']))
            elif turn.get('role') == 'assistant':
                messages.append(AIMessage(content=turn['content']))

        messages.append(HumanMessage(content=clean_message))

        response_obj = await self.llm.ainvoke(messages)
        draft = self._parse_llm_response(response_obj)

        logging.info('  - LLM Draft: %s', draft)
        state['llm_draft_response'] = draft
        state.setdefault('repair_attempts', 0)
        
        # Log prompt + draft to JSON for debugging content filters
        if self.session_logger:
            turn_count = state.get('frame_memory', {}).get('turn_count', 0)
            self.session_logger.log_prompt(
                turn_number=turn_count,
                system_prompt=state['system_prompt'],
                llm_draft=draft,
                conversation_history=state.get('conversation_history'),
            )
        
        return state

    async def _validate_output_node(self, state: FrameContext) -> FrameContext:
        """The fourth node, corresponding to Slot 3.

        Runs the `validate_output` method for each frame and stores the
        results. Runs them concurrently for maximum efficiency.
        """
        logging.info('--- SLOT 4: Validate Output ---')

        # --- DEBUGGING: Print the draft response before validation ---
        print(f"\n--- DRAFT TO VALIDATE ---\n{state['llm_draft_response']}\n-------------------------\n")
        # ---------------------------------------------------------

        validation_tasks = [frame.validate_output(state) for frame in self.frames]
        results = await asyncio.gather(*validation_tasks)

        validation_results = {}
        has_catastrophic_failure = False

        for i, frame in enumerate(self.frames):
            result = results[i]
            if result['action'] == ValidationAction.FAIL:
                has_catastrophic_failure = True
                logging.error(
                    "  - Frame '%s' validation FAILED catastrophically: %s",
                    frame.name, result.get('feedback', 'No feedback')
                )
            elif result['action'] != ValidationAction.PASS:
                logging.warning(
                    "  - Frame '%s' validation FAILED: %s (%s)",
                    frame.name, result['action'].name, result.get('feedback', 'No feedback')
                )
            validation_results[frame.name] = result

            # Log validation result
            if self.session_logger:
                self.session_logger.log_slot(
                    'validate_output', frame.name,
                    details={
                        'action': result['action'].value,
                        'feedback': result.get('feedback'),
                    },
                )

        state['validation_results'] = validation_results

        # Set fallback response here (in the node) rather than in the decision function.
        # This keeps the decision function pure and side-effect free.
        if has_catastrophic_failure:
            state['llm_draft_response'] = FALLBACK_RESPONSE

        return state

    async def _repair_output_node(self, state: FrameContext) -> FrameContext:
        """The fifth node, corresponding to Slot 4.

        Runs the `repair_output` method for frames that requested a `FIX`
        and prepares feedback for frames that requested a `REVISE`.
        """
        logging.info('--- SLOT 4b: Repair Output ---')
        state['repair_attempts'] += 1
        current_draft = state.get('llm_draft_response', '')
        needs_regeneration = False

        repair_tasks = []
        frames_to_repair = []
        for frame in self.frames:
            result = state['validation_results'].get(frame.name)
            if result and result['action'] == ValidationAction.FIX:
                repair_tasks.append(frame.repair_output(state))
                frames_to_repair.append(frame)
            elif result and result['action'] == ValidationAction.REVISE:
                needs_regeneration = True

        if repair_tasks:
            repaired_drafts = await asyncio.gather(*repair_tasks)
            # For simplicity, we'll take the result of the first repair.
            # A more complex strategy could be needed if multiple frames FIX.
            current_draft = repaired_drafts[0]
            logging.info("  - Frame '%s' applied FIX.", frames_to_repair[0].name)

        state['llm_draft_response'] = current_draft
        feedback_for_llm = []
        for frame_name, result in state['validation_results'].items():
            if result['action'] != ValidationAction.PASS:
                feedback_for_llm.append(f"- From frame '{frame_name}': {result['feedback']}")

        if needs_regeneration:
            logging.info('  - Action: REVISE. Re-generating with feedback.')
            feedback_prompt = (
                '\n\nThe previous response was not suitable. Please revise it based on the following feedback:\n'
                + '\n'.join(feedback_for_llm)
                + '\n\nPlease generate a new, corrected response.'
            )
            state['system_prompt'] += feedback_prompt

        return state

    # --- Conditional Edge Logic ---

    def _decide_on_validation(self, state: FrameContext) -> str:
        """Determines the next step after the validation node.

        Note: This is a pure decision function. State mutations happen in nodes.
        """
        validation_results = state['validation_results'].values()

        # Decision 1: Catastrophic failure. If any frame returns FAIL,
        # we immediately abort the turn. The fallback response is set
        # in the validate_output node before reaching this decision.
        if any(res['action'] == ValidationAction.FAIL for res in validation_results):
            logging.error('  - Validation detected FAIL. Aborting turn.')
            return 'finish'

        # Decision 2: Success. If all frames PASS, the turn is successful.
        if all(res['action'] == ValidationAction.PASS for res in validation_results):
            logging.info('  - All validations passed. Finishing.')
            return 'finish'

        # Decision 3: Max attempts reached. If validation failed but we've
        # already tried to repair it, we give up to avoid infinite loops.
        if state.get('repair_attempts', 0) >= MAX_REPAIR_ATTEMPTS:
            logging.warning('  - Max repair attempts reached. Finishing with last draft.')
            return 'finish'

        # Decision 4: Proceed to repair. If validation failed and we still
        # have attempts left, move to the repair node.
        logging.info('  - Validation failed. Proceeding to repair.')
        return 'repair'

    def _decide_after_repair(self, state: FrameContext) -> str:
        """Determines the next step after the repair node."""
        validation_results = state['validation_results'].values()

        # Decision 1: Regenerate. If any frame requested a REVISE, the prompt
        # has been updated with feedback. We must go back to the generation
        # node to get a new response from the LLM.
        if any(res['action'] == ValidationAction.REVISE for res in validation_results):
            logging.info('  - REVISE requested. Regenerating LLM response.')
            return 'regenerate'

        # Decision 2: Re-validate. If frames only requested FIX, the draft
        # response was modified programmatically. We should now re-run
        # validation on this newly fixed draft.
        if any(res['action'] == ValidationAction.FIX for res in validation_results):
            logging.info('  - FIX applied. Re-validating the repaired response.')
            return 'validate'

        # Fallback: This path indicates a logic error, as the repair node
        # should only be reached if a FIX or REVISE was requested. We fail safe.
        logging.error('  - Invalid state in repair decision. Aborting turn.')
        return 'fail'

    async def ainvoke(
        self,
        user_input: str,
        conversation_history: list[dict],
        frame_memory: dict
    ) -> dict[str, Any]:
        """Runs the entire frame pipeline for a single user turn, asynchronously.

        This is the main public entry point for the FrameEngine. It is a pure
        function that does not modify its inputs.

        Args:
            user_input: The user's message for the current turn.
            conversation_history: The existing conversation history.
            frame_memory: The persistent memory object for the active frames.

        Returns:
            A dictionary containing the final response and the updated state,
            including the new `conversation_history` and `frame_memory`.
        """
        # Create an immutable copy of the history to avoid side effects.
        history_copy = list(conversation_history)

        initial_state = FrameContext(
            user_input=user_input,
            conversation_history=history_copy,
            frame_memory=frame_memory,
            shared_context={},
            prompt_sections=[],
            system_prompt='',
            llm_draft_response='',
            validation_results={},
            repair_attempts=0
        )

        final_state = await self.graph.ainvoke(initial_state)

        final_response = final_state.get('llm_draft_response') or FALLBACK_RESPONSE

        # Use the cleaned message when constructing the new history.
        shared_context = final_state.get('shared_context', {})
        clean_message = shared_context.get(CLEANED_MESSAGE_KEY, user_input)

        # Log the dialogue turn (NORMAL level - visible in both NORMAL and VERBOSE)
        if self.session_logger:
            # Extract speaker and turn info from Marty's analysis
            marty_analysis = shared_context.get('mnemonic_co_creator_marty', {})
            speaker = marty_analysis.get('speaker', shared_context.get('_speaker', 'Unknown'))
            turn_number = marty_analysis.get('turn_count', frame_memory.get('turn_count', 0))

            # --- Capture Phase Information for Logging ---
            # Get memory from the correct namespace
            marty_memory = final_state.get('frame_memory', {}).get('mnemonic_co_creator_marty', final_state.get('frame_memory', {}))
            phase = marty_memory.get("session_phase", 1)
            elapsed_time = marty_memory.get("elapsed_time_minutes", 0)
            
            turn_metadata = {
                'session_phase': phase,
                'elapsed_time_minutes': elapsed_time
            }

            # Extract per-turn analysis from the shared context to enrich the log
            per_turn_analysis = shared_context.get(PER_TURN_COMPREHENSION_KEY)
            analysis_data = (
                {PER_TURN_COMPREHENSION_KEY: per_turn_analysis}
                if per_turn_analysis
                else None
            )

            self.session_logger.log_turn(
                turn_number=turn_number,
                speaker=speaker,
                user_message=clean_message,
                assistant_response=final_response,
                analysis_data=analysis_data,
                metadata=turn_metadata,
            )

        # Construct the new history without modifying the original.
        new_history = history_copy + [
            {'role': 'user', 'content': clean_message},
            {'role': 'assistant', 'content': final_response},
        ]
        final_state['conversation_history'] = new_history

        return {
            'response': final_response,
            'final_state': final_state
        }

    async def end_session(self, final_state: FrameContext) -> None:
        """Saves the session log with the final frame memory.

        This should be called after the conversation loop is finished to ensure
        the complete session is logged.

        Args:
            final_state: The very last state returned by the ainvoke method.
        """
        if self.session_logger:
            logging.info('--- SESSION END ---')
            self.session_logger.save(
                frame_memory=final_state.get('frame_memory'),
                generate_markdown_report=True,
            )
            logging.info(
                'Session saved to: %s',
                self.session_logger.output_dir
                / f'session_{self.session_logger.session_id}.yaml',
            )
