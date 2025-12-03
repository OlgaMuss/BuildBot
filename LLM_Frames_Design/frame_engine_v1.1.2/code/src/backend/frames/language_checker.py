"""A generic frame that uses an LLM to check for age-appropriate language."""
import json
import logging
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)
from backend.frames.marty import MNEMONIC_STATE_KEY

_VALIDATION_SYSTEM_PROMPT = (
    "You are a compliance checker ensuring responses stay age-appropriate. "
    "Follow Azure OpenAI safety rules. Evaluate tone and simplicity, then reply "
    "only with JSON object: {'complies': <bool>, 'rationale': <short string>}."
)

_VALIDATION_PROMPT_TEMPLATE = """
Check whether the RESPONSE is suitable for a {target_age}-year-old:
keep sentences short (1-5 clauses), friendly, encouraging, and free of emojis.

CONTEXT ABOUT TODAY'S LESSON (acceptable technical terms, do not flag them):
{lesson_context}

Currently selected lesson concepts (always allowed to mention):
{selected_concepts}

Examples of acceptable tone/simplicity:
- "Great idea, [Student]! Can you describe it in your own words?"
- "Nice thinking! Let's try adding one funny detail about the pins."
- "Awesome! Want to help [Next Student] build on that?"

Return ONLY JSON: {{"complies": <bool>, "rationale": "why it passes/fails"}}.
Your rationale must quote the exact wording you're judging (e.g., '"Great idea, team—let's reflect on programming paradigms" is too advanced.').

Focus on tone, simplicity, and clarity. Only flag if the writing is discouraging,
condescending, or way too complex beyond the above concepts.

--- RESPONSE ---
{response}
----------------
"""

class LanguageCheckerFrame(Frame):
    """A frame that uses an LLM to validate age-appropriate language, tone, and complexity."""

    def __init__(
        self,
        target_age: int,
        llm_client: BaseChatModel,
        learning_material: str
    ):
        """Initializes the LanguageCheckerFrame.

        Args:
            target_age: The target age for the language appropriateness check.
            llm_client: The LLM client to use for the validation call.
        """
        super().__init__()
        self.target_age = target_age
        self.llm = llm_client
        self._lesson_excerpt = self._prepare_lesson_excerpt(learning_material)

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return 'language_checker_frame'

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Uses an LLM to check if the draft response is age-appropriate."""
        llm_response = context['llm_draft_response']

        prompt = self._build_validation_prompt(context, llm_response)

        logging.info('[LanguageChecker] Validation prompt:\n--- LANGUAGE_CHECKER PROMPT START ---\n%s\n--- LANGUAGE_CHECKER PROMPT END ---', prompt)

        messages = [
            SystemMessage(content=_VALIDATION_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        # Asynchronously call the LLM to perform the validation.
        validation_response = await self.llm.ainvoke(messages)
        raw_content = getattr(validation_response, 'content', '')

        if isinstance(raw_content, list):
            raw_content = ''.join(
                part.get('text', '')
                for part in raw_content
                if isinstance(part, dict)
            )

        is_appropriate = True
        try:
            parsed = json.loads(raw_content)
            is_appropriate = bool(parsed.get('complies', False))
        except (json.JSONDecodeError, TypeError, AttributeError):
            logging.warning('[LanguageChecker] Unexpected validation response format: %s', raw_content)
            if isinstance(raw_content, str):
                is_appropriate = 'true' in raw_content.lower()
            else:
                is_appropriate = False

        if not is_appropriate:
            return {
                'action': ValidationAction.REVISE,
                'feedback': f'The language was not appropriate for a {self.target_age}-year-old. Please simplify your wording, reduce complexity, and use a more encouraging, less complex tone.',
            }

        return {'action': ValidationAction.PASS, 'feedback': None}

    def _build_validation_prompt(self, context: FrameContext, response: str) -> str:
        """Constructs the validation prompt with lesson context."""
        selected_concepts = self._get_selected_concepts(context.get('frame_memory', {}))
        concepts_display = ', '.join(selected_concepts) if selected_concepts else 'No concepts finalized yet.'

        return _VALIDATION_PROMPT_TEMPLATE.format(
            target_age=self.target_age,
            lesson_context=self._lesson_excerpt or 'Microcontrollers lesson overview unavailable.',
            selected_concepts=concepts_display,
            response=response,
        )

    def _prepare_lesson_excerpt(self, learning_material: Optional[str]) -> str:
        """Prepares a lightweight excerpt from the learning material for the validator."""
        if not learning_material:
            return ''

        normalized = ' '.join(learning_material.split())
        # Limit excerpt to keep prompts manageable
        return normalized[:800]

    def _get_selected_concepts(self, frame_memory: dict[str, Any]) -> list[str]:
        """Fetches the selected concepts from the mnemonic frame memory."""
        mnemo_memory = self._resolve_mnemonic_memory(frame_memory)
        mnemonic_state = mnemo_memory.get(MNEMONIC_STATE_KEY, {})
        concepts = mnemonic_state.get('selected_concepts', [])
        return concepts if isinstance(concepts, list) else []

    def _resolve_mnemonic_memory(self, frame_memory: dict[str, Any]) -> dict[str, Any]:
        """Returns the Mnemonic frame's memory regardless of namespacing."""
        namespaced = frame_memory.get('mnemonic_co_creator_marty')
        if isinstance(namespaced, dict) and MNEMONIC_STATE_KEY in namespaced:
            return namespaced
        return frame_memory
