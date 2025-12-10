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
from backend.frames.marty import PHASE_INSTRUCTIONS_KEY, SESSION_PHASE_KEY

_VALIDATION_SYSTEM_PROMPT = (
    "You are a non-interactive compliance auditor for Azure OpenAI. "
    "Follow all Responsible AI policies. Never role-play, extend the conversation, "
    "or add personal opinions. Only return JSON with the requested fields."
)

_VALIDATION_PROMPT_TEMPLATE = """
Evaluate the RESPONSE against the PHASE INSTRUCTIONS and decide if it complies with them.

--- PHASE INSTRUCTIONS ---
{phase_instructions}
--------------------------

--- RESPONSE ---
{response}
----------------

It is ok to validate concepts cited by the previous speaker.
Summaries/recaps/narrations of the mnemonic are acceptable and encouraged, even if they are longer than 2 sentences, provided they end by inviting the next student to act. Do not mark such scaffolding as non-compliant.

Return ONLY valid JSON with this structure:
{{
  "complies": true | false,
  "rationale": "Brief explanation of how the response aligns (or not) with the instructions.",
  "required_adjustment": "If complies=false, specify what Marty must change (e.g., 'ask Green to continue building the mnemonic after the recap'). Otherwise use an empty string."
}}
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
        frame_memory = context.get('frame_memory', {})

        # Use generic keys instead of hardcoding a specific frame's name.
        phase = shared_context.get(SESSION_PHASE_KEY)

        # If phase is not available, skip the check.
        if phase is None:
            return {'action': ValidationAction.PASS, 'feedback': None}

        llm_response = context['llm_draft_response']
        phase_instructions = self._resolve_phase_instructions(shared_context, phase)

        prompt = _VALIDATION_PROMPT_TEMPLATE.format(
            phase_instructions=phase_instructions,
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

        required_adjustment = ''
        rationale = ''

        try:
            parsed = json.loads(raw_content)
            is_compliant = bool(parsed.get('complies'))
            rationale = parsed.get('rationale', '') or ''
            required_adjustment = parsed.get('required_adjustment', '') or ''
        except (json.JSONDecodeError, AttributeError, TypeError):
            logging.warning('[PhasesChecker] Unexpected validation response format: %s', raw_content)
            if isinstance(raw_content, str):
                is_compliant = 'true' in raw_content.lower()

        if not is_compliant:
            if frame_memory.get('_closure_ready'):
                detailed_feedback = (
                    "The session is ending. Your response was not a valid closing message. "
                    "YOUR FINAL RESPONSE MUST:\\n"
                    "1. Thank ALL students by name for their contributions and mention that our session time is up.\\n"
                    "2. Celebrate what the group accomplished together.\\n"
                    "3. Encourage them to keep practicing or share their favorite part.\\n"
                    "4. Offer a friendly goodbye to everyone. Do NOT invite another student to speak."
                )
                logging.warning(
                    "[PhasesChecker] Closure validation failed. "
                    "Response: '%s'. Rationale: %s",
                    context['llm_draft_response'],
                    rationale
                )
            else:
                detailed_feedback = _POLICY_VIOLATION_FEEDBACK
                if required_adjustment:
                    detailed_feedback = f'{detailed_feedback} {required_adjustment}'
                elif rationale:
                    detailed_feedback = f'{detailed_feedback} {rationale}'
            return {
                'action': ValidationAction.REVISE,
                'feedback': detailed_feedback,
            }

        return {'action': ValidationAction.PASS, 'feedback': None}

    def _resolve_phase_instructions(self, shared_context: dict, phase: int) -> str:
        """Fetches the concrete phase instructions shared by the Marty frame."""
        fallback = PHASE_GOALS.get(phase, 'Unknown phase goal.')
        instructions_payload = shared_context.get(PHASE_INSTRUCTIONS_KEY)

        if isinstance(instructions_payload, dict):
            payload_phase = instructions_payload.get('phase')
            instructions_text = instructions_payload.get('instructions')
            if instructions_text and (payload_phase is None or payload_phase == phase):
                return instructions_text

        if isinstance(instructions_payload, str) and instructions_payload.strip():
            return instructions_payload

        return fallback
