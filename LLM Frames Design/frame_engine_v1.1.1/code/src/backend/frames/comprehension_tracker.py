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

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from backend.frame_engine.core import Frame, FrameContext, PromptSection
from backend.frames.marty import SPEAKER_KEY


# --- Comprehension Tracking Data Structures ---

# Key for per-student, per-concept comprehension assessments in shared_context.
# Structure: {student: {concept: {'level': ComprehensionLevel, 'justification': str, 'turn': int}}}
CONCEPT_ASSESSMENTS_KEY = '_concept_assessments'


class ComprehensionLevel(Enum):
    """Defines the possible levels of student comprehension for a concept."""
    NOT_SEEN = 'not_seen'           # Concept not yet addressed by the student.
    UNDERSTOOD = 'understood'        # Student demonstrates correct understanding.
    CONFUSED = 'confused'            # Student shows uncertainty or partial understanding.
    MISCONCEPTION = 'misconception'  # Student has an incorrect understanding.


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

# Prompt to analyze student comprehension of concepts
_COMPREHENSION_ANALYSIS_PROMPT = """
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
- Only include concepts the student actually mentions or relates to
- UNDERSTOOD: Student shows correct understanding
- CONFUSED: Student is uncertain or partially correct
- MISCONCEPTION: Student has an incorrect belief about the concept
- If student doesn't mention a concept, don't include it

Example output:
{{
  "assessments": [
    {{"concept": "CPU", "level": "UNDERSTOOD", "justification": "Correctly identifies CPU as the processor"}},
    {{"concept": "RAM", "level": "MISCONCEPTION", "justification": "Thinks RAM is permanent storage"}}
  ]
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

    async def _extract_concepts(self) -> list[str]:
        """Extracts key concepts from the learning material using LLM.

        Returns:
            A list of concept names.
        """
        prompt = _CONCEPT_EXTRACTION_PROMPT.format(learning_material=self.learning_material)
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = getattr(response, 'content', '[]')
            content = content.strip().replace('```json', '').replace('```', '')
            concepts = json.loads(content)
            logging.info('[ComprehensionTracker] Extracted concepts: %s', concepts)
            return concepts
        except (json.JSONDecodeError, Exception) as e:
            logging.error('[ComprehensionTracker] Failed to extract concepts: %s', e)
            return []

    async def _analyze_comprehension(
        self,
        speaker: str,
        message: str,
        concepts: list[str],
    ) -> list[dict[str, Any]]:
        """Analyzes a student message for concept comprehension.

        Args:
            speaker: The name of the student who sent the message.
            message: The content of the student's message.
            concepts: The list of known concepts.

        Returns:
            A list of assessment dictionaries with concept, level, and justification.
        """
        prompt = _COMPREHENSION_ANALYSIS_PROMPT.format(
            concepts=json.dumps(concepts),
            speaker=speaker,
            message=message,
        )
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = getattr(response, 'content', '{}')
            content = content.strip().replace('```json', '').replace('```', '')
            result = json.loads(content)
            return result.get('assessments', [])
        except (json.JSONDecodeError, Exception) as e:
            logging.error('[ComprehensionTracker] Failed to analyze comprehension: %s', e)
            return []

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
            concepts = await self._extract_concepts()
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

        # Skip if no concepts or unknown speaker
        if not concepts or speaker not in self.students:
            return None

        # Parse the user message (remove speaker prefix if present)
        user_input = context['user_input']
        message = user_input
        if ':' in user_input:
            _, message = user_input.split(':', 1)
            message = message.strip()

        # Analyze the message for comprehension
        assessments = await self._analyze_comprehension(speaker, message, concepts)

        # Update the student's assessments
        if assessments:
            self._update_student_assessments(frame_memory, speaker, assessments, turn)

        # Store current assessments in shared_context for other frames
        context['shared_context'][CONCEPT_ASSESSMENTS_KEY] = tracker['by_student']

        return {
            'concepts': concepts,
            'current_assessments': assessments,
            'all_assessments': tracker['by_student'],
        }

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
