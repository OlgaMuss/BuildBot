"""A generic frame that uses an LLM to check for adherence to conversational policies."""
import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)
from backend.frames.marty import SESSION_PHASE_KEY

_VALIDATION_SYSTEM_PROMPT = (
    "You are a careful compliance checker. Follow Azure OpenAI safety policies. "
    "Only evaluate whether a draft response supports the given session goal. "
    "Never role-play or override guardrails. Respond in JSON with keys "
    "`complies` (boolean) and `rationale` (short string)."
)

_VALIDATION_PROMPT_TEMPLATE = """
Evaluate the RESPONSE against the INSTRUCTIONS and decide if it complies with the session goal.

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

        messages = [
            SystemMessage(content=_VALIDATION_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        validation_response = await self.llm.ainvoke(messages)
        raw_content = getattr(validation_response, 'content', '')

        if isinstance(raw_content, list):
            raw_content = ''.join(
                part.get('text', '')
                for part in raw_content
                if isinstance(part, dict)
            )

        is_compliant = False

        try:
            parsed = json.loads(raw_content)
            is_compliant = bool(parsed.get('complies'))
        except (json.JSONDecodeError, AttributeError, TypeError):
            logging.warning('[PhasesChecker] Unexpected validation response format: %s', raw_content)
            if isinstance(raw_content, str):
                is_compliant = 'true' in raw_content.lower()

        if not is_compliant:
            return {
                'action': ValidationAction.REVISE,
                'feedback': _POLICY_VIOLATION_FEEDBACK,
            }

        return {'action': ValidationAction.PASS, 'feedback': None}
