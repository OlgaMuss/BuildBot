"""A generic frame that uses an LLM to check for age-appropriate language."""
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)

_VALIDATION_PROMPT = """
You are a validation AI. Your task is to determine if the following RESPONSE is
written in a style and vocabulary appropriate for a {target_age}-year-old.
The tone should be encouraging and simple, and the complexity should be adequate for the {target_age}-year-old.
The response must not be condescending.
The response must NOT contain any emojis.

Your answer must be a single word: either "true" or "false".

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

        messages = [HumanMessage(content=prompt)]

        # Asynchronously call the LLM to perform the validation.
        validation_response = await self.llm.ainvoke(messages)
        is_appropriate_str = getattr(validation_response, 'content', '').lower().strip()

        if 'false' in is_appropriate_str:
            return {
                'action': ValidationAction.REVISE,
                'feedback': f'The language was not appropriate for a {self.target_age}-year-old. Please simplify your wording, reduce complexity, and use a more encouraging, less complex tone.',
            }

        return {'action': ValidationAction.PASS, 'feedback': None}
