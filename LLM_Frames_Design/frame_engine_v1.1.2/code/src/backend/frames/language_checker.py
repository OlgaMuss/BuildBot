"""A generic frame that uses an LLM to check for age-appropriate language."""
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

_VALIDATION_SYSTEM_PROMPT = (
    "You are a compliance checker ensuring responses stay age-appropriate. "
    "Follow Azure OpenAI safety rules. Evaluate tone and simplicity, then reply "
    "only with JSON object: {'complies': <bool>, 'rationale': <short string>}."
)

_VALIDATION_PROMPT = """
Check whether the RESPONSE is suitable for a {target_age}-year-old: clear vocabulary,
encouraging tone, non-condescending, and no emojis.

--- RESPONSE ---
{response}
----------------
"""


class LanguageCheckerFrame(Frame):
    """A frame that uses an LLM to validate age-appropriate language, tone, and complexity."""

    def __init__(self, target_age: int, llm_client: BaseChatModel):
        """Initializes the LanguageCheckerFrame.

        Args:
            target_age: The target age for the language appropriateness check.
            llm_client: The LLM client to use for the validation call.
        """
        super().__init__()
        self.target_age = target_age
        self.llm = llm_client

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return 'language_checker_frame'

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Uses an LLM to check if the draft response is age-appropriate."""
        llm_response = context['llm_draft_response']

        prompt = _VALIDATION_PROMPT.format(
            target_age=self.target_age,
            response=llm_response,
        )

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
