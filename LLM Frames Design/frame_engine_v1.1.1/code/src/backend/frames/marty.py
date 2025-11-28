"""A frame that facilitates a collaborative mnemonic creation session.

Exports:
    CLEANED_MESSAGE_KEY: Shared context key for cleaned user message.
    SPEAKER_KEY: Shared context key for speaker name.
    SESSION_PHASE_KEY: Shared context key for session phase.
    SUGGESTED_NEXT_SPEAKER_KEY: Shared context key for suggested next speaker.
    CONSECUTIVE_SAME_SPEAKER_KEY: Shared context key for monopolization detection.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    PromptSection,
    ValidationAction,
    ValidationResult,
)


# --- Shared Context Keys (exported for use by other frames) ---
# These keys define the data this frame writes to shared_context.

# Key for the cleaned/parsed user message.
CLEANED_MESSAGE_KEY = '_cleaned_message'

# Key for the primary speaker name (in multi-user scenarios).
SPEAKER_KEY = '_speaker'

# Key for session phase (1, 2, 3...) used by phase-aware frames.
SESSION_PHASE_KEY = '_session_phase'

# Key for suggested next speaker (for turn-taking management).
SUGGESTED_NEXT_SPEAKER_KEY = '_suggested_next_speaker'

# Key for consecutive same speaker count (for monopolization detection).
CONSECUTIVE_SAME_SPEAKER_KEY = '_consecutive_same_speaker'

# --- Constants for Clarity (Avoid Magic Strings) ---
_USER_INPUT_PATTERN = re.compile(r'\[\d{2}:\d{2}:\d{2}\]\s*(\w+):\s*(.*)')
_SESSION_LOG_INIT_MSG = 'New session started.'

_ANALYSIS_PROMPT_TEMPLATE = """
You are an expert AI assistant analyzing a single turn in a collaborative learning session.
Your goal is to provide a structured analysis of the student's message.
Your output MUST be a valid JSON object. Do not add any text before or after the JSON.

**CONTEXT:**
- Topic: {topic}
- Mnemonic Type: {mnemonic_type}
- Current Turn: {turn_count}
- Session Phase: {session_phase}
- Conversation History:
{history}

**STUDENT MESSAGE:**
"{speaker}: {message}"

**ANALYSIS TASK:**
Analyze the student's message and provide the following in a JSON object:
1.  `contribution_type`: Classify the message. Choose one:
    "mnemonic_suggestion", "knowledge_statement", "question", "builds_on_idea", "off_topic".
2.  `is_relevant`: A boolean (`true` or `false`) indicating if the message is relevant.
3.  `mnemonic_progress`: A brief summary of the current state of the mnemonic.
4.  `summary`: A one-sentence summary of the student's message.

**JSON OUTPUT EXAMPLE:**
{{
  "contribution_type": "mnemonic_suggestion",
  "is_relevant": true,
  "mnemonic_progress": "The group has established the main character but not the plot yet.",
  "summary": "The student suggests a creative way to link two concepts for the story."
}}
"""


class MnemonicCoCreatorFrame(Frame):
    """A frame that guides students to collaboratively create a mnemonic."""

    def __init__(
        self,
        topic: str,
        learning_material: str,
        students: list[str],
        mnemonic_type: str,
        phase_config: dict[str, int],
        llm_client: BaseChatModel,
    ):
        """Initializes the MnemonicCoCreatorFrame.

        Args:
            topic: The central theme of the mnemonic session.
            learning_material: The source text for the mnemonic.
            students: A list of student names participating in the session.
            mnemonic_type: The type of mnemonic to be created (e.g., 'Story').
            phase_config: A dictionary defining the turn boundaries for each phase.
            llm_client: The LLM client to use for internal analysis tasks.
        """
        super().__init__()
        self.topic = topic
        self.learning_material = learning_material
        self.students = students
        self.mnemonic_type = mnemonic_type
        self.phases = phase_config
        self.llm = llm_client
        self.session_id = f"{self.topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return 'mnemonic_co_creator_marty'

    # --- Helper Methods for Analyze Input (Single Responsibility) ---

    def _initialize_memory(self, frame_memory: dict[str, Any]) -> None:
        """Sets up the initial state in `frame_memory` for a new session."""
        frame_memory['turn_count'] = 0
        frame_memory['session_phase'] = 1
        frame_memory['consecutive_off_topic_turns'] = 0
        frame_memory['session_start_time'] = datetime.now().isoformat()
        frame_memory['last_turn_time'] = None
        # Track turn order for fair distribution
        frame_memory['recent_speakers'] = []  # Last N speakers (for turn-taking)
        frame_memory['participation'] = {
            student: {
                'contribution_count': 0,
                'total_speaking_time_seconds': 0.0,
                'last_contribution_time': None,
            }
            for student in self.students
        }
        self._log_event(_SESSION_LOG_INIT_MSG)
        logging.info('New session started. ID: %s', self.session_id)

    def _parse_user_input(self, user_input: str) -> tuple[str, str]:
        """Extracts the speaker's name and their message from the raw input string."""
        match = _USER_INPUT_PATTERN.match(user_input)
        if match:
            return match.group(1), match.group(2).strip()
        # Fallback for unformatted input (e.g., from Streamlit)
        if ':' in user_input:
            speaker, message = user_input.split(':', 1)
            if speaker in self.students:
                return speaker, message.strip()
        return 'Unknown', user_input

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
        recent_speakers = frame_memory['recent_speakers']
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
        if speaker in frame_memory['participation']:
            participation = frame_memory['participation'][speaker]
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
        counts = [
            data['contribution_count']
            for data in frame_memory['participation'].values()
        ]
        if not counts or max(counts) < 2:
            return []

        min_contributions = min(counts)
        if (max(counts) - min_contributions) < 2:
            return []

        return [
            name
            for name, data in frame_memory['participation'].items()
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
        recent_speakers = frame_memory['recent_speakers']
        participation = frame_memory['participation']

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
                participation[s]['contribution_count'],
                participation[s]['total_speaking_time_seconds'],
            )
        )

        return candidates[0] if candidates else None

    # --- Main Slot Implementations ---

    async def analyze_input(
        self, context: FrameContext
    ) -> Optional[dict[str, Any]]:
        """Parses user input, manages session state, and tracks participation."""
        frame_memory = context['frame_memory']
        user_input = context['user_input']

        if 'turn_count' not in frame_memory:
            self._initialize_memory(frame_memory)

        # Update turn count and session phase
        frame_memory['turn_count'] += 1
        turn = frame_memory['turn_count']
        phase = self._get_current_phase(turn)
        frame_memory['session_phase'] = phase

        speaker, message = self._parse_user_input(user_input)

        # Track participation, speaking time, and turn order
        participation_analysis = self._update_participation(frame_memory, speaker, message)

        # Perform the deep analysis using an LLM call.
        llm_analysis = await self._run_llm_analysis(
            context, speaker, message, turn, phase
        )

        # Track off-topic duration
        if llm_analysis.get('is_relevant') is False:
            frame_memory['consecutive_off_topic_turns'] += 1
        else:
            frame_memory['consecutive_off_topic_turns'] = 0

        # Consolidate all findings for shared_context.
        analysis_output = {
            'turn_count': turn,
            'speaker': speaker,
            'message': message,
            'participation': frame_memory['participation'],
            'session_phase': phase,
            'off_topic_duration': frame_memory['consecutive_off_topic_turns'],
            'recent_speakers': frame_memory['recent_speakers'],
            **participation_analysis,  # underparticipating_students, suggested_next_speaker, etc.
            **llm_analysis,  # understanding_level, contribution_type, is_relevant, etc.
        }

        # Store data in the shared context using well-known keys.
        # This allows other frames to access it without hardcoding this frame's name.
        context['shared_context'][CLEANED_MESSAGE_KEY] = message
        context['shared_context'][SPEAKER_KEY] = speaker
        context['shared_context'][SESSION_PHASE_KEY] = phase
        context['shared_context'][SUGGESTED_NEXT_SPEAKER_KEY] = participation_analysis.get(
            'suggested_next_speaker'
        )
        context['shared_context'][CONSECUTIVE_SAME_SPEAKER_KEY] = participation_analysis.get(
            'consecutive_same_speaker', 0
        )

        self._log_event('Analysis complete.')
        return analysis_output

    def _get_current_phase(self, turn_count: int) -> int:
        """Determines the current session phase based on the turn count."""
        if turn_count <= self.phases.get('phase_1_end', 5):
            return 1
        elif turn_count <= self.phases.get('phase_2_end', 20):
            return 2
        return 3

    async def _run_llm_analysis(
        self, context: FrameContext, speaker: str, message: str, turn: int, phase: int
    ) -> dict[str, Any]:
        """Uses an LLM to perform a deep analysis of the user's input.

        This internal method is the core of the frame's intelligence. It
        constructs a specialized prompt to ask an LLM to classify the user's
        contribution, assess their understanding, and check for relevance.
        This structured data is then used by the `get_prompt_sections` slot to
        create a highly context-aware prompt for the main LLM call.

        Args:
            context: The full `FrameContext` of the current turn.
            speaker: The name of the student who is speaking.
            message: The content of the student's message.
            turn: The current turn number.
            phase: The current session phase.

        Returns:
            A dictionary containing the structured analysis from the LLM.
        """
        history_str = json.dumps(context['conversation_history'], indent=2)
        prompt = _ANALYSIS_PROMPT_TEMPLATE.format(
            topic=self.topic,
            mnemonic_type=self.mnemonic_type,
            turn_count=turn,
            session_phase=phase,
            history=history_str,
            speaker=speaker,
            message=message,
        )

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            analysis_json = getattr(response, 'content', '{}')
            # Clean the response to ensure it's valid JSON
            analysis_json = analysis_json.strip().replace('```json', '').replace('```', '')
            return json.loads(analysis_json)
        except (json.JSONDecodeError, Exception) as e:
            logging.error('Failed to parse LLM analysis response: %s', e)
            # Return a default, safe structure on failure
            return {
                'contribution_type': 'unknown',
                'is_relevant': True,
                'summary': 'Analysis failed.',
            }

    async def get_prompt_sections(self, context: FrameContext) -> list[PromptSection]:
        """Constructs the prompt sections based on the current session phase."""
        analysis = context['shared_context'].get(self.name, {})
        phase = analysis.get('session_phase', 1)
        underparticipating_students = analysis.get('underparticipating_students')
        suggested_next_speaker = analysis.get('suggested_next_speaker')
        consecutive_same_speaker = analysis.get('consecutive_same_speaker', 0)
        off_topic_duration = analysis.get('off_topic_duration', 0)

        sections: list[PromptSection] = []

        # Section 1: Base persona and knowledge
        sections.append({
            'label': 'Marty - Persona & Knowledge',
            'content': self._get_base_prompt(),
        })

        # Section 2: Phase-specific instructions
        sections.append({
            'label': f'Marty - Phase {phase} Instructions',
            'content': self._get_phase_instructions(phase),
        })

        # Section 3: Turn-taking management (if needed)
        turn_taking_content = self._get_turn_taking_instructions(
            underparticipating_students,
            suggested_next_speaker,
            consecutive_same_speaker,
        )
        if turn_taking_content:
            sections.append({
                'label': 'Marty - Turn Management',
                'content': turn_taking_content,
            })

        # Section 4: Relevance management (if needed)
        relevance_content = self._get_relevance_instructions(off_topic_duration)
        if relevance_content:
            sections.append({
                'label': 'Marty - Redirection',
                'content': relevance_content,
            })

        return sections

    def _get_base_prompt(self) -> str:
        """Returns the static, core part of the system prompt."""
        return f"""You are 'Marty,' a friendly and encouraging buddy robot facilitating a session \
for students to create a mnemonic about '{self.topic}'.
Your response must be concise (1-3 sentences) and focus on only 1-2 concepts per turn.
Base all your factual knowledge *exclusively* on the following material:
--- LEARNING MATERIAL ---
{self.learning_material.strip()}
-------------------------"""

    def _get_phase_instructions(self, phase: int) -> str:
        """Returns the instructional part of the prompt for the current phase."""

        # Add specific structural guidance based on the chosen mnemonic type.
        type_guidance = ''
        if self.mnemonic_type == 'Story':
            type_guidance = (
                'Help the students create a coherent narrative '
                'that weaves all key concepts together.'
            )
        elif self.mnemonic_type == 'Acronym':
            type_guidance = (
                'Help the students build an acronym '
                'where each letter stands for a key concept.'
            )
        elif self.mnemonic_type == 'Song':
            type_guidance = (
                'Help the students write rhyming lines for a song '
                'that each capture a key concept.'
            )

        if phase == 1:
            return """Current Goal: Collective Hook & Knowledge Building.
Your task is to facilitate a whole-group discussion. Ask open questions that help \
students identify what they know about the topic and what's unclear."""
        elif phase == 2:
            return f"""Current Goal: Brainstorm Core Concepts.
Your task is to guide the students to select the 3-5 most critical concepts \
for their '{self.mnemonic_type}' mnemonic.
{type_guidance}"""
        return f"""Current Goal: Memorization & Practice.
Your task is to test the students' recall of the mnemonic. Ask them to recite parts \
or fill in the blanks. Encourage them to help each other remember.
{type_guidance}"""

    def _get_turn_taking_instructions(
        self,
        underparticipating: Optional[list[str]],
        suggested_next: Optional[str],
        consecutive_same: int,
    ) -> str:
        """Generates instructions for fair turn-taking and participation balance.

        Args:
            underparticipating: Students who have contributed significantly less.
            suggested_next: The recommended next speaker for fairness.
            consecutive_same: How many times the current speaker has spoken in a row.

        Returns:
            A string with turn-taking instructions, or empty string if none needed.
        """
        instructions = []

        # Handle monopolization: same person speaking multiple times in a row
        if consecutive_same >= 3:
            instructions.append(
                'The same student has been speaking for several turns in a row. '
                'Encourage others to contribute by asking: "What do the rest of you think?"'
            )
        elif consecutive_same == 2:
            if suggested_next:
                instructions.append(
                    f"Let's hear from someone else. Try asking: "
                    f"'{suggested_next}, what are your thoughts on this?'"
                )

        # Handle underparticipation
        if underparticipating and not instructions:
            student_list = ' and '.join(underparticipating)
            instructions.append(
                f'Gently invite {student_list} to share their thoughts, '
                f"for example: 'What do you think about this, {underparticipating[0]}?'"
            )

        return '\n'.join(instructions)

    def _get_relevance_instructions(self, off_topic_duration: int) -> str:
        """Generates an instruction to redirect if the conversation is off-topic."""
        if off_topic_duration < 2:
            return ''
        return (
            'The conversation has been off-topic for a couple of turns. '
            'Gently redirect the conversation back to the task of creating the mnemonic.'
        )

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Validates the LLM's response for conciseness."""
        llm_response = context['llm_draft_response']

        # This frame is now only responsible for checking the length of the
        # response. The check for direct answers has been moved to the
        # specialized AnswerCheckerFrame.
        if len(llm_response.split()) > 50:
            return {
                'action': ValidationAction.REVISE,
                'feedback': 'Your response is too long. Keep it to 1-3 sentences.',
            }

        return {'action': ValidationAction.PASS, 'feedback': None}

    async def repair_output(self, context: FrameContext) -> str:
        """This frame relies on the REVISE action and does not implement programmatic fixes.

        In a more complex scenario, this slot could be used to perform simple,
        deterministic repairs on the `llm_draft_response`. For this frame, we
        let the default behavior (returning the draft unmodified) suffice and
        rely on providing feedback for a full regeneration.

        Args:
            context: The current turn's `FrameContext`.

        Returns:
            The original, unmodified `llm_draft_response`.
        """
        return context['llm_draft_response']

    def _log_event(self, message: str) -> None:
        """Logs an internal frame event for debugging.

        Note: Session logging is now handled by the FrameEngine's SessionLogger.
        This method is for internal debugging only.

        Args:
            message: A description of the event.
        """
        logging.debug('[Marty] %s', message)
