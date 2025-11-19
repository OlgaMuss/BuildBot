"""A generic frame that uses an LLM to check if a response is a direct answer."""
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)

# A specialized, lean prompt for the validation LLM call.
_VALIDATION_PROMPT = """
You are a validation AI. Your task is to determine if the following RESPONSE is a
direct quote or a very close paraphrase from the provided SOURCE MATERIAL.

Your answer must be a single word: either "true" or "false".

--- SOURCE MATERIAL ---
{source_material}
---------------------

--- RESPONSE ---
{response}
----------------
"""


class AnswerCheckerFrame(Frame):
    """A frame that uses an LLM to validate if a response is a direct answer."""

    def __init__(self, learning_material: str, llm_client: BaseChatModel):
        """Initializes the AnswerCheckerFrame.

        Args:
            learning_material: The source text to check against for direct answers.
            llm_client: The LLM client to use for the validation call.
        """
        super().__init__()
        self.learning_material = learning_material
        self.llm = llm_client

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return "answer_checker_frame"

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Uses an LLM to check if the draft response is a direct answer."""
        llm_response = context["llm_draft_response"]

        # Construct the prompt for our validation LLM call.
        prompt = _VALIDATION_PROMPT.format(
            source_material=self.learning_material,
            response=llm_response,
        )
        
        messages = [HumanMessage(content=prompt)]

        # Asynchronously call the LLM to perform the validation.
        validation_response = await self.llm.ainvoke(messages)
        
        is_direct_answer_str = getattr(validation_response, "content", "").lower().strip()

        if "true" in is_direct_answer_str:
            return {
                "action": ValidationAction.REVISE,
                "feedback": "Do not give a direct answer from the learning material. Instead, ask a question that prompts the students to find the answer themselves.",
            }

        return {"action": ValidationAction.PASS, "feedback": None}
