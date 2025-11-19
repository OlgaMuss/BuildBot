"""A generic frame that uses an LLM to check for adherence to conversational policies."""
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)

_VALIDATION_PROMPT_TEMPLATE = """
You are a validation AI. Your task is to determine if the provided RESPONSE strictly adheres to the given INSTRUCTIONS.

Your answer must be a single word: either "true" or "false".

--- INSTRUCTIONS ---
The response must adhere to the following policies:
1.  **Tone:** Be friendly, encouraging, and not condescending.
2.  **Phase Goal:** The response must be appropriate for the current goal: '{phase_goal}'.
3.  **Complexity:** The language and concepts must be suitable for a student with an '{understanding_level}' understanding of the topic.
--------------------

--- RESPONSE ---
{response}
----------------
"""


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
        return "policy_checker_frame"

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Uses an LLM to check if the draft response follows key policies."""
        marty_analysis = context.get("shared_context", {}).get("mnemonic_co_creator_marty", {})
        
        # If Marty's analysis is not present, we cannot perform the check.
        if not marty_analysis:
            return {"action": ValidationAction.PASS, "feedback": None}

        phase = marty_analysis.get("session_phase", 1)
        understanding = marty_analysis.get("understanding_level", "intermediate")
        llm_response = context["llm_draft_response"]

        phase_goals = {
            1: "Facilitate a whole-group discussion to build knowledge.",
            2: "Guide the collaborative creation of the mnemonic.",
            3: "Test and practice the recall of the created mnemonic."
        }
        
        prompt = _VALIDATION_PROMPT_TEMPLATE.format(
            phase_goal=phase_goals.get(phase, "Unknown"),
            understanding_level=understanding,
            response=llm_response,
        )

        messages = [HumanMessage(content=prompt)]
        validation_response = await self.llm.ainvoke(messages)
        is_compliant_str = getattr(validation_response, "content", "").lower().strip()

        if "false" in is_compliant_str:
            return {
                "action": ValidationAction.REVISE,
                "feedback": "The response did not adhere to one of the core policies (Tone, Phase Goal, or Complexity). Please regenerate it to be more encouraging, better match the session goal, and be appropriate for the student's understanding level.",
            }

        return {"action": ValidationAction.PASS, "feedback": None}
