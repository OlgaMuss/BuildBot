"""A generic frame that uses an LLM to check for adherence to conversational policies."""
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)
from backend.frames.marty import SESSION_PHASE_KEY

_VALIDATION_PROMPT_TEMPLATE = """
You are a validation AI. Your task is to determine if the provided RESPONSE strictly adheres to the given INSTRUCTIONS.

Your answer must be a single word: either "true" or "false".

--- INSTRUCTIONS ---
The response must be appropriate for the current goal: '{phase_goal}'.
--------------------

--- RESPONSE ---
{response}
----------------
"""

PHASE_GOALS = {
    1: 'Facilitate a whole-group discussion to build knowledge.',
    2: 'Guide the collaborative creation of the mnemonic.',
    3: 'Test and practice the recall of the created mnemonic.',
}

_POLICY_VIOLATION_FEEDBACK = (
    'The response did not adhere to the Phase Goal. '
    'Please regenerate it to better match the session goal.'
)


class PhasesCheckerFrame(Frame):
    """A frame that uses an LLM to validate adherence to phase goals."""

    def __init__(self, llm_client: BaseChatModel):
        """Initializes the PhasesCheckerFrame.

        Args:
            llm_client: The LLM client to use for the validation call.
        """
        super().__init__()
        self.llm = llm_client

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return 'phases_checker_frame'

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Uses an LLM to check if the draft response follows key policies."""
        shared_context = context.get('shared_context', {})

        # Use generic keys instead of hardcoding a specific frame's name.
        phase = shared_context.get(SESSION_PHASE_KEY)

        # If phase is not available, skip the check.
        if phase is None:
            return {'action': ValidationAction.PASS, 'feedback': None}

        llm_response = context['llm_draft_response']

        prompt = _VALIDATION_PROMPT_TEMPLATE.format(
            phase_goal=PHASE_GOALS.get(phase, 'Unknown'),
            response=llm_response,
        )

        logging.info('[PhasesChecker] Validation prompt:\n--- PHASES_CHECKER PROMPT START ---\n%s\n--- PHASES_CHECKER PROMPT END ---', prompt)

        messages = [HumanMessage(content=prompt)]
        validation_response = await self.llm.ainvoke(messages)
        is_compliant_str = getattr(validation_response, 'content', '').lower().strip()

        if 'false' in is_compliant_str:
            return {
                'action': ValidationAction.REVISE,
                'feedback': _POLICY_VIOLATION_FEEDBACK,
            }

        return {'action': ValidationAction.PASS, 'feedback': None}
