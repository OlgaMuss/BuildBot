"""A frame that tracks student comprehension at the concept level.

This frame analyzes student messages to assess their understanding of specific
concepts from the learning material. It maintains per-student, per-concept
assessments that are updated at each turn.

Exports:
    ComprehensionLevel: Enum for comprehension levels.
    ConceptAssessment: TypedDict for per-concept assessments.
    CONCEPT_ASSESSMENTS_KEY: Shared context key for assessments.
"""
import json
import logging
from enum import Enum
from typing import Any, Optional, TypedDict
import asyncio

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
# System reminder for all validation-like LLM calls
_AZURE_POLICY_SYSTEM_PROMPT = (
    "You must follow Azure OpenAI safety and content management policies. "
    "If a request conflicts with those policies, respond conservatively or refuse."
)

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    PromptSection,
    ValidationAction,
    ValidationResult,
)
from backend.frames.marty import CLEANED_MESSAGE_KEY, SPEAKER_KEY, MNEMONIC_STATE_KEY

# --- Comprehension Tracking Data Structures ---

# Key for per-student, per-concept comprehension assessments in shared_context.
# Structure: {student: {concept: {'level': ComprehensionLevel, 'justification': str, 'turn': int}}}
CONCEPT_ASSESSMENTS_KEY = '_concept_assessments'

# Key for the granular, per-turn analysis of concept understanding.
# This captures what was understood/confused in the *current* message only.
# Structure: {'understood': list[str], 'confused': list[str]}
PER_TURN_COMPREHENSION_KEY = '_per_turn_comprehension'


class ComprehensionLevel(Enum):
    """Defines the possible levels of student comprehension for a concept."""
    NOT_SEEN = 'not_seen'           # Concept not yet addressed by the student.
    UNDERSTOOD = 'understood'        # Student demonstrates correct understanding.
    CONFUSED = 'confused'            # Student shows uncertainty or partial understanding.
    MISCONCEPTION = 'misconception'  # Student has an incorrect understanding.


class PerTurnComprehension(TypedDict):
    """Represents the concepts understood or confused in a single turn."""
    understood: list[str]
    confused: list[str]


class ConceptAssessment(TypedDict):
    """Assessment of a student's comprehension of a specific concept.

    This is stored per-student, per-concept in frame_memory and shared via
    CONCEPT_ASSESSMENTS_KEY in shared_context.
    """
    level: ComprehensionLevel
    justification: Optional[str]
    turn: Optional[int]


# Prompt to extract key concepts from learning material (run once at session start)
_CONCEPT_EXTRACTION_PROMPT = """
You are an expert educator. Extract the key concepts from this learning material.
Return ONLY a JSON array of concept names (strings), nothing else.

LEARNING MATERIAL:
{learning_material}

Example output: ["CPU", "RAM", "GPIO", "Flash Memory"]
"""

# Prompt for the session-long comprehension analysis (existing prompt)
_CUMULATIVE_COMPREHENSION_ANALYSIS_PROMPT = """
You are an expert educator analyzing a student's understanding.
Based on their message, assess their comprehension of the concepts they mention.

KNOWN CONCEPTS (from learning material):
{concepts}

STUDENT MESSAGE:
"{speaker}: {message}"

For each concept the student mentions or demonstrates knowledge about, provide an assessment.
Your output MUST be a valid JSON object with this structure:
{{
  "assessments": [
    {{
      "concept": "concept_name",
      "level": "UNDERSTOOD|CONFUSED|MISCONCEPTION",
      "justification": "Brief explanation of why this level was assigned"
    }}
  ]
}}

Rules:
- ONLY include concepts where the student DEMONSTRATES something about their understanding
- UNDERSTOOD: Student correctly explains, applies, or describes the concept
- CONFUSED: Student explicitly expresses uncertainty, asks a question, or makes a partially correct statement
- MISCONCEPTION: Student states something factually incorrect about the concept
- Do NOT include concepts the student merely mentions without demonstrating understanding or confusion
- Saying "we need to learn about X" or "our topic is X" does NOT count as confusion - it's just stating a task

Example output:
{{
  "assessments": [
    {{"concept": "CPU", "level": "UNDERSTOOD", "justification": "Correctly identifies CPU as the processor"}},
    {{"concept": "RAM", "level": "MISCONCEPTION", "justification": "Thinks RAM is permanent storage"}}
  ]
}}
"""

# New prompt for granular, per-turn comprehension analysis
_PER_TURN_COMPREHENSION_ANALYSIS_PROMPT = """
You are an expert AI analyzing a student's message in a learning session.
Your task is to identify which specific concepts the student understood or seemed confused about *in this single message*.
Your output MUST be a valid JSON object with two keys: "understood" and "confused".

**KNOWN CONCEPTS:**
{concepts}

**STUDENT MESSAGE:**
"{speaker}: {message}"

**ANALYSIS TASK:**
1.  `understood`: Create a list of concept names the student correctly explains, uses, or applies in this message.
2.  `confused`: Create a list of concept names the student asks about, uses incorrectly, or seems uncertain about in this message.

**RULES:**
- Only include concepts where the student DEMONSTRATES understanding or confusion, not just mentions.
- `understood`: Student correctly explains, applies, or describes the concept.
- `confused`: Student explicitly expresses uncertainty, asks a question about the concept, or makes a partially correct statement.
- If the student merely mentions a concept without demonstrating understanding or asking about it, do NOT include it.
- Statements like "we need to create a poem on X" or "our topic is X" are NOT confusion - they are task statements.
- If the student does not demonstrate any understanding or confusion, return empty lists for both.

**JSON OUTPUT EXAMPLE:**
{{
  "understood": ["CPU", "Flash Memory"],
  "confused": ["RAM"]
}}
"""


class ComprehensionTrackerFrame(Frame):
    """A frame that tracks per-student, per-concept comprehension over time."""

    def __init__(self, learning_material: str, students: list[str], llm_client: BaseChatModel):
        """Initializes the ComprehensionTrackerFrame.

        Args:
            learning_material: The source text to extract concepts from.
            students: List of student names to track.
            llm_client: The LLM client for concept extraction and analysis.
        """
        super().__init__()
        self.learning_material = learning_material
        self.students = students
        self.llm = llm_client

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return 'comprehension_tracker_frame'

    def _initialize_memory(self, frame_memory: dict[str, Any], concepts: list[str]) -> None:
        """Initializes the comprehension tracking structure in frame_memory.

        Args:
            frame_memory: The persistent memory dictionary.
            concepts: List of concepts extracted from learning material.
        """
        frame_memory['comprehension_tracker'] = {
            'concepts': concepts,
            'by_student': {
                student: {
                    concept: {
                        'level': ComprehensionLevel.NOT_SEEN.value,
                        'justification': None,
                        'turn': None,
                    }
                    for concept in concepts
                }
                for student in self.students
            },
        }
        logging.info(
            '[ComprehensionTracker] Initialized tracking for %d concepts and %d students',
            len(concepts),
            len(self.students),
        )

    async def _extract_concepts(self, context: FrameContext) -> list[str]:
        """Returns the student-selected concepts once they exist."""
        frame_memory = context.get('frame_memory', {})
        mnemonic_state = frame_memory.get('mnemonic_state', {})
        selected_concepts = mnemonic_state.get('selected_concepts') or []
        if selected_concepts:
            logging.info('[ComprehensionTracker] Using selected concepts: %s', selected_concepts)
        else:
            logging.info('[ComprehensionTracker] No selected concepts available yet.')
        return selected_concepts

    async def _analyze_cumulative_comprehension(
        self,
        speaker: str,
        message: str,
        concepts: list[str],
    ) -> list[dict[str, Any]]:
        """Analyzes a student message for concept comprehension to build a cumulative profile.

        Args:
            speaker: The name of the student who sent the message.
            message: The content of the student's message.
            concepts: The list of known concepts.

        Returns:
            A list of assessment dictionaries with concept, level, and justification.
        """
        if not concepts:
            return []

        prompt = _CUMULATIVE_COMPREHENSION_ANALYSIS_PROMPT.format(
            concepts=json.dumps(concepts),
            speaker=speaker,
            message=message,
        )
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=_AZURE_POLICY_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            content = getattr(response, 'content', '{}')
            content = content.strip().replace('```json', '').replace('```', '')
            result = json.loads(content)
            return result.get('assessments', [])
        except (json.JSONDecodeError, Exception) as e:
            logging.error('[ComprehensionTracker] Failed to analyze cumulative comprehension: %s', e)
            return []

    async def _analyze_per_turn_comprehension(
        self,
        speaker: str,
        message: str,
        concepts: list[str],
    ) -> PerTurnComprehension:
        """Analyzes a student message to find concepts understood/confused in this turn.

        Args:
            speaker: The name of the student who sent the message.
            message: The content of the student's message.
            concepts: The list of known concepts.

        Returns:
            A dictionary with 'understood' and 'confused' concept lists.
        """
        if not concepts:
            return {'understood': [], 'confused': []}

        prompt = _PER_TURN_COMPREHENSION_ANALYSIS_PROMPT.format(
            concepts=json.dumps(concepts),
            speaker=speaker,
            message=message,
        )
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=_AZURE_POLICY_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            content = getattr(response, 'content', '{}')
            content = content.strip().replace('```json', '').replace('```', '')
            result = json.loads(content)
            return {
                'understood': result.get('understood', []),
                'confused': result.get('confused', []),
            }
        except (json.JSONDecodeError, Exception) as e:
            logging.error('[ComprehensionTracker] Failed to analyze per-turn comprehension: %s', e)
            return {'understood': [], 'confused': []}

    def _update_student_assessments(
        self,
        frame_memory: dict[str, Any],
        speaker: str,
        assessments: list[dict[str, Any]],
        turn: int,
    ) -> None:
        """Updates the comprehension assessments for a student.

        Args:
            frame_memory: The persistent memory dictionary.
            speaker: The student whose assessments are being updated.
            assessments: List of new assessments from the LLM analysis.
            turn: The current turn number.
        """
        tracker = frame_memory.get('comprehension_tracker', {})
        student_data = tracker.get('by_student', {}).get(speaker, {})

        for assessment in assessments:
            concept = assessment.get('concept')
            level_str = assessment.get('level', '').upper()
            justification = assessment.get('justification', '')

            # Map string to enum value
            level_map = {
                'UNDERSTOOD': ComprehensionLevel.UNDERSTOOD.value,
                'CONFUSED': ComprehensionLevel.CONFUSED.value,
                'MISCONCEPTION': ComprehensionLevel.MISCONCEPTION.value,
            }
            level = level_map.get(level_str)

            if concept and level and concept in student_data:
                student_data[concept] = {
                    'level': level,
                    'justification': justification,
                    'turn': turn,
                }
                logging.debug(
                    '[ComprehensionTracker] Updated %s/%s: %s',
                    speaker,
                    concept,
                    level,
                )

    async def analyze_input(self, context: FrameContext) -> Optional[dict[str, Any]]:
        """Analyzes student input and updates comprehension tracking.

        On the first turn, extracts concepts from learning material.
        On every turn, analyzes the student's message for concept comprehension.
        """
        frame_memory = context['frame_memory']
        shared_context = context.get('shared_context', {})

        # Get speaker from shared_context (set by Marty frame)
        speaker = shared_context.get(SPEAKER_KEY, 'Unknown')

        # Get turn count from frame_memory (set by Marty frame)
        turn = frame_memory.get('turn_count', 1)

        # Initialize on first turn
        if 'comprehension_tracker' not in frame_memory:
            concepts = await self._extract_concepts(context)
            if concepts:
                self._initialize_memory(frame_memory, concepts)
            else:
                # Fallback: empty tracker if extraction fails
                frame_memory['comprehension_tracker'] = {
                    'concepts': [],
                    'by_student': {},
                }
                return None

        tracker = frame_memory['comprehension_tracker']
        concepts = tracker.get('concepts', [])
        mnemo_memory = self._resolve_mnemonic_memory(frame_memory)
        selected_concepts = mnemo_memory.get(MNEMONIC_STATE_KEY, {}).get('selected_concepts', [])
        if selected_concepts and set(selected_concepts) != set(concepts):
            tracker['concepts'] = selected_concepts
            concepts = selected_concepts

        # Skip if no concepts or unknown speaker
        if not concepts or speaker not in self.students:
            return None

        # Get the cleaned message from shared_context, falling back to raw input.
        # This is better than parsing it again here.
        message = shared_context.get(CLEANED_MESSAGE_KEY, context['user_input'])

        # --- Run Both Comprehension Analyses Concurrently ---
        cumulative_assessments_task = self._analyze_cumulative_comprehension(
            speaker, message, concepts
        )
        per_turn_comprehension_task = self._analyze_per_turn_comprehension(
            speaker, message, concepts
        )

        cumulative_assessments, per_turn_comprehension = await asyncio.gather(
            cumulative_assessments_task, per_turn_comprehension_task
        )

        # Update the cumulative student assessments
        if cumulative_assessments:
            self._update_student_assessments(
                frame_memory, speaker, cumulative_assessments, turn
            )

        # Store the granular, per-turn analysis in shared_context for other frames
        context['shared_context'][PER_TURN_COMPREHENSION_KEY] = per_turn_comprehension

        # Store current cumulative assessments in shared_context as well
        context['shared_context'][CONCEPT_ASSESSMENTS_KEY] = tracker['by_student']

        # The frame's return value for logging/debugging
        return {
            'concepts': concepts,
            'per_turn_analysis': per_turn_comprehension,
            'cumulative_assessments_updated': cumulative_assessments,
            'all_student_profiles': tracker['by_student'],
        }

    def _resolve_mnemonic_memory(self, frame_memory: dict[str, Any]) -> dict[str, Any]:
        """Returns the Mnemonic frame's memory regardless of namespacing."""
        namespaced = frame_memory.get('mnemonic_co_creator_marty')
        if isinstance(namespaced, dict) and MNEMONIC_STATE_KEY in namespaced:
            return namespaced
        return frame_memory

    async def get_prompt_sections(self, context: FrameContext) -> list[PromptSection]:
        """Adds guidance based on comprehension status.

        Includes:
        - Concepts with misconceptions or confusion (to clarify)
        - Concepts already understood (to avoid repeating)
        """
        frame_memory = context['frame_memory']
        tracker = frame_memory.get('comprehension_tracker', {})
        by_student = tracker.get('by_student', {})

        if not by_student:
            return []

        # Aggregate comprehension across all students
        to_clarify: list[str] = []
        understood: list[str] = []

        for student, concepts in by_student.items():
            for concept, data in concepts.items():
                level = data.get('level')
                justification = data.get('justification', '')

                if level == ComprehensionLevel.MISCONCEPTION.value:
                    entry = f'- {concept} ({student}): {justification}'
                    if entry not in to_clarify:
                        to_clarify.append(entry)
                elif level == ComprehensionLevel.CONFUSED.value:
                    entry = f'- {concept} ({student}): {justification}'
                    if entry not in to_clarify:
                        to_clarify.append(entry)
                elif level == ComprehensionLevel.UNDERSTOOD.value:
                    if concept not in understood:
                        understood.append(concept)

        sections: list[PromptSection] = []

        if to_clarify:
            sections.append({
                'label': 'Comprehension Tracker - Concepts to Clarify',
                'content': (
                    'The following concepts need clarification (students showed confusion or misconceptions):\n'
                    + '\n'.join(to_clarify)
                ),
            })

        if understood:
            sections.append({
                'label': 'Comprehension Tracker - Concepts Already Understood',
                'content': (
                    'The following concepts are already well understood (avoid repeating them unless necessary):\n'
                    + '\n'.join(f'- {c}' for c in understood)
                ),
            })

        return sections
