"""The core orchestration logic for the Rodin Frame Engine.

This module uses LangGraph to construct and execute a state machine that represents
the four-slot frame pipeline.
"""
import logging
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from backend.frame_engine.core import Frame, FrameContext, ValidationAction
import asyncio

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

    def __init__(self, frames: List[Frame], llm_client: BaseChatModel):
        """Initializes the FrameEngine.

        Args:
            frames: A list of instantiated Frame objects to be used in the pipeline.
            llm_client: An instantiated LangChain chat model client.
        """
        self.frames = frames
        self.llm = llm_client
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Builds the LangGraph state machine for the frame pipeline."""
        builder = StateGraph(FrameContext)

        # 1. Define Nodes
        builder.add_node("analyze_input", self._analyze_input_node)
        builder.add_node("shape_prompt", self._shape_prompt_node)
        builder.add_node("generate_response", self._generate_response_node)
        builder.add_node("validate_output", self._validate_output_node)
        builder.add_node("repair_output", self._repair_output_node)

        # 2. Define Edges
        builder.set_entry_point("analyze_input")
        builder.add_edge("analyze_input", "shape_prompt")
        builder.add_edge("shape_prompt", "generate_response")
        builder.add_edge("generate_response", "validate_output")
        
        builder.add_conditional_edges(
            "validate_output",
            self._decide_on_validation,
            {
                "repair": "repair_output",
                "finish": END,
            },
        )
        
        builder.add_conditional_edges(
            "repair_output",
            self._decide_after_repair,
            {
                "regenerate": "generate_response",
                "validate": "validate_output",
                "fail": END
            }
        )

        return builder.compile()

    def get_frame(self, frame_name: str) -> Optional[Frame]:
        """Retrieves a frame by its unique name.
        
        Args:
            frame_name: The unique name of the frame to retrieve.
            
        Returns:
            The Frame object with the given name, or None if not found.
        """
        for frame in self.frames:
            if frame.name == frame_name:
                return frame
        return None

    # --- Node Implementations ---

    async def _analyze_input_node(self, state: FrameContext) -> FrameContext:
        """The first node in the graph, corresponding to Slot 1.
        
        It runs the `analyze_input` method for each frame and populates the
        `shared_context`.
        """
        logging.info("--- SLOT 1: Analyze Input ---")
        shared_context = {}
        for frame in self.frames:
            result = await frame.analyze_input(state)
            if result:
                shared_context[frame.name] = result
                logging.info("  - Frame '%s' analysis: %s", frame.name, result)
            else:
                shared_context[frame.name] = {}
        state["shared_context"] = shared_context
        return state

    async def _shape_prompt_node(self, state: FrameContext) -> FrameContext:
        """The second node, corresponding to Slot 2.
        
        It sequentially runs the `shape_prompt` method for each frame,
        accumulating the final system prompt.
        """
        logging.info("--- SLOT 2: Shape Prompt ---")
        current_prompt = state.get("system_prompt", "")
        for frame in self.frames:
            current_prompt = await frame.shape_prompt(state)
            state["system_prompt"] = current_prompt
        logging.info("  - System prompt shaped successfully.")
        logging.debug("  - Final System Prompt:\n---\n%s\n---", current_prompt)
        state["system_prompt"] = current_prompt
        return state
    
    def _parse_llm_response(self, response: Any) -> str:
        """Extracts the string content from a potentially complex LLM response object."""
        # The response might be a simple string, an AIMessage, or a more
        # complex object with a `content` attribute. This helper handles them.
        if isinstance(response, str):
            return response
        
        draft = getattr(response, "content", "")
        if isinstance(draft, list):
            # Handle cases where content is a list of parts (e.g., multimodal)
            return "".join(
                part.get("text", "")
                for part in draft
                if isinstance(part, dict)
            )
        if not draft and hasattr(response, "text"):
            return response.text
        
        return draft

    async def _generate_response_node(self, state: FrameContext) -> FrameContext:
        """The third node, which calls the LLM.
        
        It constructs the message history and sends the request to the LLM,
        storing the output in `llm_draft_response`.
        """
        logging.info("--- SLOT 3: Generate ---")
        prompt = state["system_prompt"]
        history = state["conversation_history"]

        # Use the clean, parsed message from the analysis slot, not the raw input.
        marty_analysis = state.get("shared_context", {}).get("mnemonic_co_creator_marty", {})
        clean_message = marty_analysis.get("message", state["user_input"])

        messages = [SystemMessage(content=prompt)]
        for turn in history:
            if turn.get("role") == "user":
                messages.append(HumanMessage(content=turn["content"]))
            elif turn.get("role") == "assistant":
                messages.append(AIMessage(content=turn["content"]))

        messages.append(HumanMessage(content=clean_message))

        response_obj = await self.llm.ainvoke(messages)
        draft = self._parse_llm_response(response_obj)

        logging.info("  - LLM Draft: %s", draft)
        state["llm_draft_response"] = draft
        state.setdefault("repair_attempts", 0)
        return state

    async def _validate_output_node(self, state: FrameContext) -> FrameContext:
        """The fourth node, corresponding to Slot 3.
        
        It runs the `validate_output` method for each frame and stores the
        results. It runs them concurrently for maximum efficiency.
        """
        logging.info("--- SLOT 4: Validate Output ---")
        
        validation_tasks = [frame.validate_output(state) for frame in self.frames]
        results = await asyncio.gather(*validation_tasks)
        
        validation_results = {}
        for i, frame in enumerate(self.frames):
            result = results[i]
            if result["action"] != ValidationAction.PASS:
                logging.warning(
                    "  - Frame '%s' validation FAILED: %s (%s)",
                    frame.name, result['action'].name, result.get('feedback', 'No feedback')
                )
            validation_results[frame.name] = result
        state["validation_results"] = validation_results
        return state

    async def _repair_output_node(self, state: FrameContext) -> FrameContext:
        """The fifth node, corresponding to Slot 4.
        
        It runs the `repair_output` method for frames that requested a `FIX`
        and prepares feedback for frames that requested a `REVISE`.
        """
        logging.info("--- SLOT 4b: Repair Output ---")
        state["repair_attempts"] += 1
        current_draft = state.get("llm_draft_response", "")
        needs_regeneration = False

        repair_tasks = []
        frames_to_repair = []
        for frame in self.frames:
            result = state["validation_results"].get(frame.name)
            if result and result["action"] == ValidationAction.FIX:
                repair_tasks.append(frame.repair_output(state))
                frames_to_repair.append(frame)
            elif result and result["action"] == ValidationAction.REVISE:
                needs_regeneration = True
        
        if repair_tasks:
            repaired_drafts = await asyncio.gather(*repair_tasks)
            # For simplicity, we'll take the result of the first repair.
            # A more complex strategy could be needed if multiple frames FIX.
            current_draft = repaired_drafts[0]
            logging.info("  - Frame '%s' applied FIX.", frames_to_repair[0].name)

        state["llm_draft_response"] = current_draft
        feedback_for_llm = []
        for frame_name, result in state["validation_results"].items():
            if result["action"] != ValidationAction.PASS:
                feedback_for_llm.append(f"- From frame '{frame_name}': {result['feedback']}")

        if needs_regeneration:
            logging.info("  - Action: REVISE. Re-generating with feedback.")
            
            # Construct a forceful, direct instruction for the LLM.
            # Prepending this to the system prompt is more effective than appending.
            feedback_intro = (
                "IMPERATIVE CORRECTION: The previous response had a critical error. "
                "You MUST follow this instruction to fix it:\n"
            )
            feedback_body = "\n".join(f"- {feedback}" for feedback in feedback_for_llm)
            
            correction_prompt = f"{feedback_intro}{feedback_body}\n\n---\n\n"
            
            # Prepend the correction to the original system prompt.
            state["system_prompt"] = correction_prompt + state["system_prompt"]

        return state

    # --- Conditional Edge Logic ---

    def _decide_on_validation(self, state: FrameContext) -> str:
        """Determines the next step after the validation node."""
        validation_results = state["validation_results"].values()

        # Decision 1: Catastrophic failure. If any frame returns FAIL,
        # we immediately abort the turn with a fallback response.
        if any(res["action"] == ValidationAction.FAIL for res in validation_results):
            logging.error("  - Validation detected FAIL. Aborting turn.")
            state["llm_draft_response"] = FALLBACK_RESPONSE
            return "finish"

        # Decision 2: Success. If all frames PASS, the turn is successful.
        if all(res["action"] == ValidationAction.PASS for res in validation_results):
            logging.info("  - All validations passed. Finishing.")
            return "finish"

        # Decision 3: Max attempts reached. If validation failed but we've
        # already tried to repair it, we give up to avoid infinite loops.
        if state.get("repair_attempts", 0) >= MAX_REPAIR_ATTEMPTS:
            logging.warning("  - Max repair attempts reached. Finishing with last draft.")
            return "finish"
        
        # Decision 4: Proceed to repair. If validation failed and we still
        # have attempts left, move to the repair node.
        logging.info("  - Validation failed. Proceeding to repair.")
        return "repair"

    def _decide_after_repair(self, state: FrameContext) -> str:
        """Determines the next step after the repair node."""
        validation_results = state["validation_results"].values()

        # Decision 1: Regenerate. If any frame requested a REVISE, the prompt
        # has been updated with feedback. We must go back to the generation
        # node to get a new response from the LLM.
        if any(res["action"] == ValidationAction.REVISE for res in validation_results):
            logging.info("  - REVISE requested. Regenerating LLM response.")
            return "regenerate"

        # Decision 2: Re-validate. If frames only requested FIX, the draft
        # response was modified programmatically. We should now re-run
        # validation on this newly fixed draft.
        if any(res["action"] == ValidationAction.FIX for res in validation_results):
            logging.info("  - FIX applied. Re-validating the repaired response.")
            return "validate"

        # Fallback: This path indicates a logic error, as the repair node
        # should only be reached if a FIX or REVISE was requested. We fail safe.
        logging.error("  - Invalid state in repair decision. Aborting turn.")
        return "fail"

    async def ainvoke(self, user_input: str, conversation_history: List[Dict], frame_memory: Dict) -> Dict[str, Any]:
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
            system_prompt="",
            llm_draft_response="",
            validation_results={},
            repair_attempts=0
        )

        final_state = await self.graph.ainvoke(initial_state)

        final_response = final_state.get("llm_draft_response") or FALLBACK_RESPONSE

        # Also use the clean message when constructing the new history.
        marty_analysis = final_state.get("shared_context", {}).get("mnemonic_co_creator_marty", {})
        clean_message = marty_analysis.get("message", user_input)

        # Construct the new history without modifying the original.
        new_history = history_copy + [
            {"role": "user", "content": clean_message},
            {"role": "assistant", "content": final_response},
        ]
        final_state["conversation_history"] = new_history
        
        return {
            "response": final_response,
            "final_state": final_state
        }
