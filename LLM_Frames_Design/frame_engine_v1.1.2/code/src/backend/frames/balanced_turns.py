"""A frame that validates balanced turn-taking in multi-student sessions.

This frame ensures that Marty follows the turn-taking suggestions generated
by the MnemonicCoCreatorFrame to maintain fair participation balance.
"""
import logging
from typing import Optional, Any
from datetime import datetime

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    PromptSection,
    ValidationAction,
    ValidationResult,
)


# --- Shared Context Keys (exported for use by other frames) ---
# Key for suggested next speaker (for turn-taking management).
SUGGESTED_NEXT_SPEAKER_KEY = '_suggested_next_speaker'

# Key for consecutive same speaker count (for monopolization detection).
CONSECUTIVE_SAME_SPEAKER_KEY = '_consecutive_same_speaker'


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

    def _initialize_memory(self, frame_memory: dict[str, Any]) -> None:
        """Sets up the initial state for participation tracking."""
        frame_memory['recent_speakers'] = []
        frame_memory['participation'] = {
            student: {
                'contribution_count': 0,
                'total_speaking_time_seconds': 0.0,
                'last_contribution_time': None,
            }
            for student in self.students
        }
        frame_memory['suggested_next_speaker'] = None
        

    async def analyze_input(
        self, context: FrameContext
    ) -> Optional[dict[str, Any]]:
        """Parses user input, manages session state, and tracks participation."""
        # Get this frame's namespaced memory, creating it if it doesn't exist.
        my_memory = context['frame_memory'].setdefault(self.name, {})

        # Initialize memory if this is the first time the frame is running
        if 'participation' not in my_memory:
            self._initialize_memory(my_memory)

        speaker = context['shared_context'].get('_speaker', 'Unknown')
        message = context['shared_context'].get('_cleaned_message', '')

        # Track participation using this frame's own namespaced memory
        participation_analysis = self._update_participation(my_memory, speaker, message)
        
        # Store the suggestion in this frame's persistent memory so the simulation
        # script (and this frame in the next turn) can access it.
        my_memory['suggested_next_speaker'] = participation_analysis.get('suggested_next_speaker')

        # The rest is for the shared context for other frames in the *current* turn
        context['shared_context'][SUGGESTED_NEXT_SPEAKER_KEY] = participation_analysis.get(
            'suggested_next_speaker'
        )
        context['shared_context'][CONSECUTIVE_SAME_SPEAKER_KEY] = participation_analysis.get(
            'consecutive_same_speaker', 0
        )
        # The engine will automatically put this return value into shared_context[self.name]
        return participation_analysis

    async def get_prompt_sections(self, context: FrameContext) -> list[PromptSection]:
        """Provides explicit turn-taking instructions for Marty before generation."""
        shared = context.get('shared_context', {})
        previous_speaker = shared.get('_speaker')
        suggested_next = shared.get(SUGGESTED_NEXT_SPEAKER_KEY)
        if not previous_speaker or not suggested_next or suggested_next == previous_speaker:
            return []

        consecutive_same = shared.get(CONSECUTIVE_SAME_SPEAKER_KEY, 0)
        extra_note = ""
        if consecutive_same >= 2:
            extra_note = (
                f"\nNOTE: {previous_speaker} has spoken {consecutive_same} times in a row. "
                "You must switch speakers now."
            )

        instructions = (
            "TURN-TAKING REMINDER:\n"
            f"- Begin by acknowledging {previous_speaker} by name.\n"
            f"- End by explicitly inviting {suggested_next} to contribute next.\n"
            "Follow both steps every turn to keep participation balanced."
            f"CRITICAL: Ask only ONE question total"
            f"{extra_note}"
        )

        return [{
            'label': 'Balanced Turns Guidance',
            'content': instructions,
        }]

    def _update_participation(
        self,
        frame_memory: dict[str, Any],
        speaker: str,
        message: str,
    ) -> dict[str, Any]:
        """Tracks student contributions, speaking time, and turn order.

        Args:
            frame_memory: The persistent memory for this frame.
            speaker: The name of the current speaker.
            message: The message content (used to estimate speaking time).

        Returns:
            A dictionary with participation analysis:
            - underparticipating_students: List of students who have spoken less
            - suggested_next_speaker: Who should ideally speak next for fairness
            - consecutive_same_speaker: How many times the same person spoke in a row
        """
        current_time = datetime.now()

        # Update turn order tracking
        recent_speakers = frame_memory.setdefault('recent_speakers', [])
        recent_speakers.append(speaker)
        # Keep only the last 5 speakers for turn-taking analysis
        if len(recent_speakers) > 5:
            recent_speakers.pop(0)

        # Count consecutive turns by the same speaker
        consecutive_same_speaker = 0
        for s in reversed(recent_speakers):
            if s == speaker:
                consecutive_same_speaker += 1
            else:
                break

        # Update participation stats for the speaker
        participation_data = frame_memory.setdefault('participation', {
            student: {
                'contribution_count': 0,
                'total_speaking_time_seconds': 0.0,
                'last_contribution_time': None,
            }
            for student in self.students
        })

        if speaker in participation_data:
            participation = participation_data[speaker]
            participation['contribution_count'] += 1
            participation['last_contribution_time'] = current_time.isoformat()

            # Estimate speaking time based on message length (rough: ~150 words/min)
            word_count = len(message.split())
            estimated_seconds = (word_count / 150) * 60
            participation['total_speaking_time_seconds'] += estimated_seconds

        # Update the last turn time for the session
        frame_memory['last_turn_time'] = current_time.isoformat()

        # Identify underparticipating students
        underparticipating = self._find_underparticipating_students(frame_memory)

        # Suggest next speaker for fair turn-taking
        suggested_next = self._suggest_next_speaker(frame_memory, speaker)

        return {
            'underparticipating_students': underparticipating,
            'suggested_next_speaker': suggested_next,
            'consecutive_same_speaker': consecutive_same_speaker,
        }

    def _find_underparticipating_students(
        self, frame_memory: dict[str, Any]
    ) -> list[str]:
        """Identifies students who have contributed significantly less than others."""
        participation = frame_memory.get('participation', {})
        counts = [
            data['contribution_count']
            for data in participation.values()
        ]
        if not counts or max(counts) < 2:
            return []

        min_contributions = min(counts)
        # Latency of 1: flag underparticipation when difference >= 1
        if (max(counts) - min_contributions) < 1:
            return []

        return [
            name
            for name, data in participation.items()
            if data['contribution_count'] == min_contributions
        ]

    def _suggest_next_speaker(
        self, frame_memory: dict[str, Any], current_speaker: str
    ) -> Optional[str]:
        """Suggests who should speak next for fair turn distribution.

        Prioritizes students who:
        1. Haven't spoken recently
        2. Have the lowest contribution count
        3. Have the least total speaking time
        """
        recent_speakers = frame_memory.get('recent_speakers', [])
        participation = frame_memory.get('participation', {})

        # Find students who haven't spoken in the last 3 turns
        recent_set = set(recent_speakers[-3:]) if len(recent_speakers) >= 3 else set(recent_speakers)
        candidates = [s for s in self.students if s not in recent_set and s != current_speaker]

        if not candidates:
            # All students have spoken recently, pick the one with least contributions
            candidates = [s for s in self.students if s != current_speaker]

        if not candidates:
            return None

        # Sort by contribution count (ascending), then by speaking time (ascending)
        candidates.sort(
            key=lambda s: (
                participation.get(s, {}).get('contribution_count', 0),
                participation.get(s, {}).get('total_speaking_time_seconds', 0.0),
            )
        )

        return candidates[0] if candidates else None
        
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

        # Find the first student name mentioned in the response.
        # This should be the previous_speaker (being acknowledged), not the next speaker.
        first_mention_idx = float('inf')
        first_mentioned = None
        for student in self.students:
            idx = response.find(student)
            if idx != -1 and idx < first_mention_idx:
                first_mention_idx = idx
                first_mentioned = student

        # The first mentioned student MUST be the previous speaker (acknowledgment comes first)
        if first_mentioned and first_mentioned != previous_speaker:
            return (
                f"TURN-TAKING ERROR: You acknowledged {first_mentioned}, but {previous_speaker} "
                f"was the one who just spoke. You must acknowledge {previous_speaker} first, "
                f"then invite {suggested_next} to contribute."
            )

        # Also verify that the previous speaker appears BEFORE the suggested next speaker
        prev_idx = response.find(previous_speaker)
        next_idx = response.find(suggested_next)

        if prev_idx != -1 and next_idx != -1 and next_idx < prev_idx:
            return (
                f"TURN-TAKING ERROR: You mentioned {suggested_next} before {previous_speaker}. "
                f"Structure your response as: 1) First acknowledge {previous_speaker} briefly. "
                f"2) Then ask ONLY {suggested_next} ONE question to invite them to contribute next."
            )
        
        # Check for multiple questions being asked (count question marks)
        question_count = response.count('?')
        if question_count > 1:
            return (
                f"TURN-TAKING ERROR: You asked {question_count} questions. "
                f"You should ask ONLY ONE question to {suggested_next}. "
                f"Structure: 1) Acknowledge {previous_speaker} briefly. "
                f"2) Ask ONLY {suggested_next} ONE question to invite them to contribute next."
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
        frame_memory = context.get('frame_memory', {})

        # Check if session is in closure mode - if so, pass validation
        if frame_memory.get('_closure_ready'):
            logging.info("[Turn Balance Validation] Closure mode detected - passing validation")
            return {'action': ValidationAction.PASS, 'feedback': None}

        # Get the suggested next speaker from the shared context (set by analyze_input)
        suggested_next = shared_context.get(SUGGESTED_NEXT_SPEAKER_KEY)
        consecutive_same = shared_context.get(CONSECUTIVE_SAME_SPEAKER_KEY, 0)
        
        # Get the speaker of the turn being analyzed from the shared context
        marty_analysis = shared_context.get('mnemonic_co_creator_marty', {})
        previous_speaker = marty_analysis.get('speaker')

        logging.info(
            f"[Turn Balance Validation] Previous: {previous_speaker}, "
            f"Suggested: {suggested_next}, Consecutive: {consecutive_same}, "
            f"Response preview: {llm_response[:100]}..."
        )

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

