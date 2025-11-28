"""A generic frame that uses an LLM to check for adherence to conversational policies."""
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)
from backend.frames.comprehension_tracker import CONCEPT_ASSESSMENTS_KEY, ComprehensionLevel
from backend.frames.marty import SESSION_PHASE_KEY

_VALIDATION_PROMPT_TEMPLATE = """
You are a validation AI. Your task is to determine if the provided RESPONSE strictly adheres to the given INSTRUCTIONS.

Your answer must be a single word: either "true" or "false".

--- INSTRUCTIONS ---
The response must adhere to the following policies:
1.  **Tone:** Be friendly, encouraging, and not condescending.
2.  **Phase Goal:** The response must be appropriate for the current goal: '{phase_goal}'.
{comprehension_instruction}
--------------------

--- RESPONSE ---
{response}
----------------
"""

_PHASE_GOALS = {
    1: 'Facilitate a whole-group discussion to build knowledge.',
    2: 'Guide the collaborative creation of the mnemonic.',
    3: 'Test and practice the recall of the created mnemonic.',
}

_POLICY_VIOLATION_FEEDBACK = (
    'The response did not adhere to one of the core policies '
    '(Tone or Phase Goal). Please regenerate it to be more '
    'encouraging and better match the session goal.'
)


class PolicyCheckerFrame(Frame):
    """A frame that uses an LLM to validate adherence to conversational policies."""

    def __init__(self, llm_client: BaseChatModel):
        """Initializes the PolicyCheckerFrame.

        Args:
            llm_client: The LLM client to use for the validation call.
        """
        super().__init__()
        self.llm = llm_client

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return 'policy_checker_frame'

    def _get_comprehension_instruction(self, assessments: dict) -> str:
        """Builds a comprehension instruction based on current assessments.

        Args:
            assessments: The per-student, per-concept assessments.

        Returns:
            A string instruction for handling misconceptions, or empty if none.
        """
        misconceptions = []
        confused = []

        for student, concepts in assessments.items():
            for concept, data in concepts.items():
                level = data.get('level')
                if level == ComprehensionLevel.MISCONCEPTION.value:
                    misconceptions.append(f'{concept} ({student})')
                elif level == ComprehensionLevel.CONFUSED.value:
                    confused.append(f'{concept} ({student})')

        if not misconceptions and not confused:
            return ''

        instruction_parts = []
        if misconceptions:
            instruction_parts.append(
                f"3.  **Address Misconceptions:** The following concepts have misconceptions that should be gently corrected: {', '.join(misconceptions)}."
            )
        if confused:
            instruction_parts.append(
                f"4.  **Clarify Confusion:** The following concepts need clarification: {', '.join(confused)}."
            )

        return '\n'.join(instruction_parts)

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Uses an LLM to check if the draft response follows key policies."""
        shared_context = context.get('shared_context', {})

        # Use generic keys instead of hardcoding a specific frame's name.
        phase = shared_context.get(SESSION_PHASE_KEY)

        # If phase is not available, skip the check.
        if phase is None:
            return {'action': ValidationAction.PASS, 'feedback': None}

        # Get concept assessments if available
        assessments = shared_context.get(CONCEPT_ASSESSMENTS_KEY, {})
        comprehension_instruction = self._get_comprehension_instruction(assessments)

        llm_response = context['llm_draft_response']

        prompt = _VALIDATION_PROMPT_TEMPLATE.format(
            phase_goal=_PHASE_GOALS.get(phase, 'Unknown'),
            comprehension_instruction=comprehension_instruction,
            response=llm_response,
        )

        messages = [HumanMessage(content=prompt)]
        validation_response = await self.llm.ainvoke(messages)
        is_compliant_str = getattr(validation_response, 'content', '').lower().strip()

        if 'false' in is_compliant_str:
            return {
                'action': ValidationAction.REVISE,
                'feedback': _POLICY_VIOLATION_FEEDBACK,
            }

        return {'action': ValidationAction.PASS, 'feedback': None}
