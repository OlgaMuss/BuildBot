"""A frame that validates balanced turn-taking in multi-student sessions.

This frame ensures that Marty follows the turn-taking suggestions generated
by the MnemonicCoCreatorFrame to maintain fair participation balance.
"""
import logging
from typing import Optional

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)

# Import shared context keys from the Marty frame
from backend.frames.marty import SUGGESTED_NEXT_SPEAKER_KEY


class BalancedTurnsFrame(Frame):
    """Validates that Marty invites the suggested next speaker when needed."""

    def __init__(self, students: list[str]):
        """Initializes the BalancedTurnsFrame.

        Args:
            students: List of student names in the session.
        """
        super().__init__()
        self.students = students

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return 'balanced_turns_validator'

    def _validate_next_speaker(
        self,
        response: str,
        previous_speaker: str,
        suggested_next: Optional[str]
    ) -> Optional[str]:
        """Validates that the response invites the suggested next speaker.

        Args:
            response: The LLM's draft response
            previous_speaker: The student who just spoke
            suggested_next: The student who should be invited (from Marty frame)

        Returns:
            An error message if validation fails, None if validation passes
        """
        # Get all student names mentioned in the response
        mentioned_students = [s for s in self.students if s in response]

        logging.debug(
            f"[Turn Balance] Previous: {previous_speaker}, "
            f"Suggested next: {suggested_next}, Mentioned: {mentioned_students}"
        )

        # No validation needed if no next speaker is suggested
        if not suggested_next or suggested_next == previous_speaker:
            return None

        # Case: Next speaker is suggested for balance
        # Check for incorrect students being invited
        miscalled_students = [
            s for s in mentioned_students 
            if s not in [previous_speaker, suggested_next]
        ]
        
        if miscalled_students:
            return (
                f"TURN-TAKING ERROR: You mentioned {', '.join(miscalled_students)}, "
                f"but for balanced participation, you should only interact with "
                f"{previous_speaker} (to acknowledge) and {suggested_next} (to invite next). "
                f"Please invite {suggested_next} to speak."
            )

        # Check if suggested_next is actually invited
        if suggested_next not in mentioned_students:
            return (
                f"TURN-TAKING ERROR: For balanced participation, you need to invite "
                f"{suggested_next} to speak next. They have participated less than others. "
                f"Please acknowledge {previous_speaker} briefly, then ask {suggested_next} a question."
            )

        # Split response to check order (acknowledge first, then invite)
        midpoint = len(response) // 2
        first_half = response[:midpoint]
        second_half = response[midpoint:]

        prev_in_second = previous_speaker in second_half
        next_in_first = suggested_next in first_half

        # Check for swapped order
        if prev_in_second and next_in_first:
            return (
                f"TURN-TAKING ERROR: You seem to have swapped the order. "
                f"You must FIRST acknowledge {previous_speaker}, "
                f"and THEN invite {suggested_next} to speak."
            )

        # Check for partial errors
        if next_in_first and previous_speaker not in first_half:
            return (
                f"TURN-TAKING ERROR: The first part of your response should acknowledge "
                f"{previous_speaker}, but you mentioned {suggested_next} instead. "
                f"Structure: 1) Acknowledge {previous_speaker}. 2) Ask {suggested_next} a question."
            )

        if prev_in_second and suggested_next not in second_half:
            return (
                f"TURN-TAKING ERROR: The second part of your response should invite "
                f"{suggested_next}, but you mentioned {previous_speaker} instead. "
                f"Structure: 1) Acknowledge {previous_speaker}. 2) Ask {suggested_next} a question."
            )

        # Validation passed
        logging.info(
            f"[Turn Balance] PASSED - Acknowledged {previous_speaker}, "
            f"invited {suggested_next}"
        )
        return None

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Validates that Marty follows turn-taking suggestions for balance.

        This frame checks that when the Marty frame suggests a specific next
        speaker (for participation balance), Marty's response actually invites
        that student.
        """
        llm_response = context['llm_draft_response']
        shared_context = context.get('shared_context', {})

        # Get turn-taking data from Marty's analysis
        marty_analysis = shared_context.get('mnemonic_co_creator_marty', {})
        previous_speaker = marty_analysis.get('speaker')
        suggested_next = shared_context.get(SUGGESTED_NEXT_SPEAKER_KEY)

        # Skip validation if no data available
        if not previous_speaker:
            return {'action': ValidationAction.PASS, 'feedback': None}

        # Validate turn-taking
        validation_error = self._validate_next_speaker(
            llm_response, previous_speaker, suggested_next
        )

        if validation_error:
            logging.warning(f"[Turn Balance Failed] {validation_error}")
            return {
                'action': ValidationAction.REVISE,
                'feedback': validation_error,
            }

        return {'action': ValidationAction.PASS, 'feedback': None}

