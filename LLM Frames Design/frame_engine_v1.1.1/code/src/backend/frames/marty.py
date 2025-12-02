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

# --- Frame Memory Keys ---
# Key for storing mnemonic creation state (concepts, finalization status, etc.)
MNEMONIC_STATE_KEY = 'mnemonic_state'

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
- Session Phase: {session_phase} (1=concept selection, 2=mnemonic creation, 3=recall practice)
- Conversation History:
{history}

**STUDENT MESSAGE:**
"{speaker}: {message}"

**ANALYSIS TASK:**
Analyze the student's message and provide the following in a JSON object:

1. `contribution_type`: Classify based on the session phase:
   - **Phase 1-2**: "mnemonic_suggestion", "knowledge_statement", "question", "builds_on_idea", "off_topic"
   - **Phase 3**: "recall_attempt" (trying to recite), "recall_question" (asking about mnemonic), "off_topic"

2. `is_relevant`: A boolean (`true` or `false`) indicating if the message is relevant.

3. `mnemonic_progress` (Phase 1-2 only) OR `recall_progress` (Phase 3 only):
   - Phase 1-2: Brief summary of the current state of mnemonic creation
   - Phase 3: Brief summary of recall attempts (e.g., "Student recited first part correctly, stuck on middle")

4. `summary`: A one-sentence summary of the student's message.


**JSON OUTPUT EXAMPLES:**
Phase 1-2:
{{
  "contribution_type": "mnemonic_suggestion",
  "is_relevant": true,
  "mnemonic_progress": "The group has established the main character but not the plot yet.",
  "summary": "The student suggests a creative way to link two concepts for the story."
}}

Phase 3:
{{
  "contribution_type": "recall_attempt",
  "is_relevant": true,
  "recall_progress": "Student recited the opening correctly: 'Once upon a time...' but paused before the CPU part.",
  "summary": "The student is attempting to recite the beginning of the story from memory."
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
        target_age: Optional[int] = None,
    ):
        """Initializes the MnemonicCoCreatorFrame.

        Args:
            topic: The central theme of the mnemonic session.
            learning_material: The source text for the mnemonic.
            students: A list of student names participating in the session.
            mnemonic_type: The type of mnemonic to be created (e.g., 'Story').
            phase_config: A dictionary defining the turn boundaries for each phase.
            llm_client: The LLM client to use for internal analysis tasks.
            target_age: The optional target age for the students.
        """
        super().__init__()
        self.topic = topic
        self.learning_material = learning_material
        self.students = students
        self.mnemonic_type = mnemonic_type
        self.phases = phase_config
        self.llm = llm_client
        self.target_age = target_age
        self.session_id = f"{self.topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # Create a dynamic regex pattern to find any of the student names at the start.
        # This is more robust for parsing AI-generated student responses.
        student_pattern = '|'.join(re.escape(s) for s in self.students)
        self._student_name_pattern = re.compile(rf'^\s*({student_pattern})\s*:\s*(.*)', re.IGNORECASE)


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
        # Track mnemonic creation state
        frame_memory['mnemonic_state'] = {
            'selected_concepts': [],      # List of concepts agreed upon for mnemonic
            'concepts_finalized': False,  # True when 3-5 concepts selected
            'mnemonic_text': '',          # The actual mnemonic story/poem/jokes
            'mnemonic_created': False,    # True when story/poem/jokes created
        }
        # Track recall attempts in Phase 3 (per student)
        frame_memory['recall_tracking'] = {
            student: {
                'attempts': 0,              # Number of times student tried to recite
                'successful_parts': [],     # Which parts they got right
                'stuck_on': [],             # Which parts they struggled with
                'last_attempt': None,       # Text of their last recall attempt
            }
            for student in self.students
        }
        self._log_event(_SESSION_LOG_INIT_MSG)
        logging.info('New session started. ID: %s', self.session_id)

    def _parse_user_input(self, user_input: str) -> tuple[str, str]:
        """Extracts the speaker's name and their message from the raw input string."""
        # First, try the strict, timestamped pattern
        strict_match = _USER_INPUT_PATTERN.match(user_input)
        if strict_match:
            return strict_match.group(1), strict_match.group(2).strip()

        # Next, try the more flexible pattern for AI-generated names
        flexible_match = self._student_name_pattern.match(user_input)
        if flexible_match:
            # Normalize the found name to the correct capitalization (e.g., 'red' -> 'Red')
            found_name = flexible_match.group(1)
            for s in self.students:
                if s.lower() == found_name.lower():
                    return s, flexible_match.group(2).strip()

        # If all else fails, return 'Unknown'
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
        # Latency of 1: flag underparticipation when difference >= 1
        if (max(counts) - min_contributions) < 1:
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
        phase = self._get_current_phase(turn, frame_memory)
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

        # Build mnemonic incrementally during Phase 2
        if phase == 2:
            contribution_type = llm_analysis.get('contribution_type', '')
            mnemonic_state = frame_memory.get(MNEMONIC_STATE_KEY, {})
            current_mnemonic = mnemonic_state.get('mnemonic_text', '')
            
            # First, check if Marty's PREVIOUS response (from last turn) has mnemonic content
            # This captures when Marty narrates or builds on the mnemonic
            if len(context['conversation_history']) > 0:
                last_message = context['conversation_history'][-1]
                if last_message.get('role') == 'assistant':
                    marty_content = await self._extract_mnemonic_content(
                        last_message.get('content', ''), 
                        'Marty'
                    )
                    if marty_content and marty_content not in current_mnemonic:
                        if current_mnemonic:
                            current_mnemonic += ' '
                        current_mnemonic += marty_content
                        logging.info(f'[Mnemonic Building] Added from Marty: {marty_content}')
            
            # Then, extract and append clean mnemonic content from student contributions
            if contribution_type in ['mnemonic_suggestion', 'builds_on_idea']:
                # Use LLM to extract just the mnemonic content (no fluff)
                clean_content = await self._extract_mnemonic_content(message, speaker)
                
                if clean_content and clean_content not in current_mnemonic:
                    # Add separator if we already have content
                    if current_mnemonic:
                        current_mnemonic += ' '
                    
                    # Append the clean mnemonic contribution
                    current_mnemonic += clean_content
                    logging.info(f'[Mnemonic Building] Added from {speaker}: {clean_content}')
            
            # Update state if we have content
            if current_mnemonic and len(current_mnemonic) > len(mnemonic_state.get('mnemonic_text', '')):
                mnemonic_state['mnemonic_text'] = current_mnemonic
                mnemonic_state['mnemonic_created'] = True
                frame_memory[MNEMONIC_STATE_KEY] = mnemonic_state
                logging.info(f'[Mnemonic Building] Current mnemonic: {current_mnemonic}')
        
        # Track recall attempts in Phase 3
        if phase == 3:
            contribution_type = llm_analysis.get('contribution_type', '')
            # Store for Phase 3 instructions to access
            frame_memory['_last_contribution_type'] = contribution_type
            
            if contribution_type in ['recall_attempt', 'recall_question']:
                recall_tracking = frame_memory.get('recall_tracking', {})
                if speaker in recall_tracking:
                    recall_tracking[speaker]['attempts'] += 1
                    recall_tracking[speaker]['last_attempt'] = message
                    # Store recall_progress from analysis
                    recall_progress = llm_analysis.get('recall_progress', '')
                    if 'correct' in recall_progress.lower() or 'recited' in recall_progress.lower():
                        recall_tracking[speaker]['successful_parts'].append(f"Turn {turn}: {recall_progress[:50]}")
                    if 'stuck' in recall_progress.lower() or 'paused' in recall_progress.lower():
                        recall_tracking[speaker]['stuck_on'].append(f"Turn {turn}: {recall_progress[:50]}")
                    frame_memory['recall_tracking'] = recall_tracking
                    logging.info(f'[Recall Tracking] {speaker} attempt #{recall_tracking[speaker]["attempts"]}: {contribution_type}')

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
        
        # Update mnemonic state based on phase transitions
        mnemonic_state = frame_memory.get(MNEMONIC_STATE_KEY, {})
        
        # When we enter Phase 2, Phase 1 is complete → extract concepts from conversation
        if phase == 2 and not mnemonic_state.get('concepts_finalized', False):
            logging.info('[Mnemonic State] Entering Phase 2 - extracting concepts from Phase 1')
            concepts_finalized, selected_concepts = await self._detect_concepts_finalized(
                context['conversation_history'], frame_memory
            )
            # Mark as finalized regardless of detection success
            mnemonic_state['concepts_finalized'] = True
            if selected_concepts:
                mnemonic_state['selected_concepts'] = selected_concepts
                logging.info(f'[Mnemonic State] Concepts extracted: {selected_concepts}')
            else:
                logging.warning('[Mnemonic State] No concepts detected, but Phase 1 is complete')
            frame_memory[MNEMONIC_STATE_KEY] = mnemonic_state
        
        # Log mnemonic state for debugging
        current_mnemonic = mnemonic_state.get('mnemonic_text', '')
        if phase == 3:
            logging.info(f'[Mnemonic State] Phase 3 - mnemonic ready: {current_mnemonic}')

        self._log_event('Analysis complete.')
        return analysis_output

    def _get_current_phase(self, turn_count: int, frame_memory: dict[str, Any]) -> int:
        """Determines the current session phase based on time AND mnemonic state.
        
        Phase transitions use BOTH time and state:
        - Phase 1 (0-3 min): Select 3-5 key concepts
        - Phase 2 (3-7 min): Create the mnemonic using those concepts
        - Phase 3 (7+ min): Practice and test recall
        
        Time provides the primary structure, state tracking ensures completion.
        """
        mnemonic_state = frame_memory.get(MNEMONIC_STATE_KEY, {})
        concepts_finalized = mnemonic_state.get('concepts_finalized', False)
        mnemonic_created = mnemonic_state.get('mnemonic_created', False)
        elapsed_time = frame_memory.get('elapsed_time_minutes', 0)
        
        # Phase 3: After 7 minutes (strict time-based transition)
        if elapsed_time >= 7:
            return 3
        
        # Phase 2: After 3 minutes (strict time-based transition)
        elif elapsed_time >= 3:
            return 2
        
        # Phase 1: First 3 minutes (concept selection)
        else:
            return 1
    
    async def _extract_mnemonic_content(self, message: str, speaker: str) -> str:
        """Uses LLM to extract just the mnemonic content from a message.
        
        Filters out conversational fluff like "What if...", "I think...", "Maybe...",
        and extracts only the actual mnemonic contribution (story/poem/joke).
        """
        extraction_prompt = f"""Extract ONLY the mnemonic content from this message. Remove all conversational phrases like "What if", "I think", "Maybe", "How about", etc.

{speaker}'s message:
{message}

Return ONLY the actual mnemonic content (the story part, poem line, or joke). If there's no mnemonic content, return nothing (empty).

Examples:
Input: "What if the pins are like arms trying to high-five everything?"
Output: The pins are like arms trying to high-five everything.

Input: "I love that idea! So the microcontroller is a chef?"
Output: The microcontroller is a chef.

Input: "Why did the chef get fired? Because he mixed up HIGH and LOW!"
Output: Why did the chef get fired? Because he mixed up HIGH and LOW!

Now extract from the message above:"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=extraction_prompt)])
            extracted = getattr(response, 'content', '').strip()
            
            if extracted and len(extracted) > 10:
                logging.info(f'[Mnemonic Extraction] Extracted from {speaker}: {extracted}')
                return extracted
            else:
                return ''
        except Exception as e:
            logging.error(f'[Mnemonic Extraction] Error extracting content: {e}')
            return ''
    
    def _extract_from_last_narration(self, conversation_history: list[dict]) -> str:
        """Extracts the mnemonic from Marty's LAST narration in Phase 2.
        
        Looks for Marty's most recent "So far, our story goes:" or similar pattern
        and extracts the complete mnemonic text after it.
        """
        # Search backwards through conversation for Marty's narrations
        narration_patterns = [
            r'So far,? our (?:story|poem|jokes?) (?:goes?|is):\s*(.*)',
            r'(?:Our|The) (?:Story|Poem|Jokes?) Mnemonic:\s*(.*)',
            r'Here\'?s? (?:the|our) (?:story|poem|jokes?) so far:\s*(.*)',
        ]
        
        for message in reversed(conversation_history):
            if message.get('role') == 'assistant':  # Marty's messages
                content = message.get('content', '')
                for pattern in narration_patterns:
                    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                    if match:
                        # Extract everything after the pattern until the next question or end
                        mnemonic_text = match.group(1).strip()
                        # Remove any trailing questions/prompts
                        mnemonic_text = re.split(r'\n\n(?:What|Who|How|Can you)', mnemonic_text)[0].strip()
                        if len(mnemonic_text) > 50:  # Sanity check: must be substantial
                            logging.info(f'[Mnemonic Extraction] Found narration: {mnemonic_text[:80]}...')
                            return mnemonic_text
        
        logging.warning('[Mnemonic Extraction] No narration found in conversation history')
        return ''
    
    async def _detect_concepts_finalized(
        self, conversation_history: list[dict], frame_memory: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Extracts concepts that students selected during Phase 1.
        
        This is called when Phase 2 starts. It looks for concepts that students
        themselves proposed, or that Marty confirmed with them.
        Returns (finalized: bool, concepts: list[str])
        """
        # Use ALL conversation history from Phase 1
        history_str = "\n".join([
            f"{msg['role']}: {msg['content']}" for msg in conversation_history
        ])
        
        prompt = f"""Analyze this Phase 1 conversation where students selected concepts for their {self.mnemonic_type} mnemonic about {self.topic}.

PHASE 1 CONVERSATION:
{history_str}

Extract the 3-5 key concepts that students PROPOSED or AGREED to use in their mnemonic.

Look for:
1. Concepts students explicitly mentioned wanting to include
2. Concepts in Marty's confirmation (e.g., "So we're using: CPU, Pins, Program")
3. Concepts students discussed as important or tricky to remember

Your response MUST be valid JSON with this structure:
{{
  "concepts": ["Concept1", "Concept2", "Concept3"]
}}

Rules:
- Prioritize student-proposed concepts over Marty's suggestions
- Extract 3-5 specific concept names (e.g., "CPU", "Pins", "Program")
- If students only discussed 1-2 concepts, extract what they chose
- Use the names/terms as students said them

Example:
{{
  "concepts": ["CPU (the brain)", "Pins (like hands)", "Program", "HIGH and LOW signals", "Power"]
}}
"""
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = getattr(response, 'content', '{}')
            content = content.strip().replace('```json', '').replace('```', '')
            result = json.loads(content)
            concepts = result.get('concepts', [])
            
            if concepts:
                logging.info(f'[Mnemonic State] Extracted {len(concepts)} student-selected concepts: {concepts}')
                return True, concepts
            else:
                logging.warning('[Mnemonic State] No concepts extracted from Phase 1')
                return True, []  # Still mark as finalized to avoid re-running
        except Exception as e:
            logging.error(f'[Mnemonic State] Failed to extract concepts: {e}')
            return True, []  # Mark as finalized to avoid re-running
    
    async def _detect_mnemonic_created(
        self, conversation_history: list[dict], frame_memory: dict[str, Any]
    ) -> tuple[bool, str]:
        """Extracts the mnemonic that students created during Phase 2.
        
        This is called when Phase 3 starts. It extracts whatever {mnemonic_type}
        students created in Phase 2, even if incomplete.
        Returns (created: bool, mnemonic_text: str)
        """
        # Use ALL conversation history to find the mnemonic
        history_str = "\n".join([
            f"{msg['role']}: {msg['content']}" for msg in conversation_history
        ])
        
        # Type-specific instructions for synthesis
        type_specific_instructions = ""
        if self.mnemonic_type == "Story":
            type_specific_instructions = """
For a STORY:
- Structure: Beginning (introduce the character/setting) → Middle (describe actions/relationships) → End (conclude the narrative)
- Include all key concepts as characters, objects, or actions in the narrative
- Use the students' analogies and metaphors (e.g., "CPU as a brain", "pins as hands")
- Create a flowing narrative with transitions between concepts
- Example structure: "Once upon a time, there was [main concept] who/that [action]. It had [component 1] and [component 2]..."
"""
        elif self.mnemonic_type == "Poem":
            type_specific_instructions = """
For a POEM:
- Create rhyming lines that each capture a key concept
- Use students' creative language and analogies
- Structure: 4-8 lines with rhyme scheme (e.g., AABB or ABAB)
- Each line should relate to a different concept or aspect
- Example: "The CPU is the brain so smart, / It makes the microcontroller start, / With pins that reach out like hands, / Following the program's commands"
"""
        elif self.mnemonic_type == "Jokes":
            type_specific_instructions = """
For JOKES:
- Create 3-5 separate jokes, each with a setup and punchline
- Each joke should focus on one key concept
- Use students' analogies as the basis for humor
- Format: "Setup question?" → "Punchline answer!"
- Example: "Why did the CPU go to school? To get a little bit smarter!" or "What did the pin say to the microcontroller? I'm ON it!"
"""
        
        prompt = f"""Analyze this Phase 2 conversation where students worked on creating a {self.mnemonic_type} mnemonic about {self.topic}.

PHASE 2 CONVERSATION:
{history_str}

Your task: Look for story elements, analogies, and narrative pieces the students proposed. SYNTHESIZE them into a coherent {self.mnemonic_type}.
{type_specific_instructions}

Your response MUST be valid JSON with this structure:
{{
  "mnemonic_text": "The synthesized {self.mnemonic_type} here"
}}

Rules for extraction:
- Identify the key analogies and story elements students suggested (e.g., "CPU is like a brain", "pins are like hands")
- SYNTHESIZE these into a proper {self.mnemonic_type} with coherent structure
- DO NOT include their questions, confusion, or discussion (e.g., "I'm still fuzzy on...")
- DO NOT just concatenate all their dialogue
- If they proposed a complete {self.mnemonic_type}, use that
- If they only proposed pieces/analogies, weave them into a short narrative
- Use their creative language and metaphors, but structure it properly
"""
        
        # Add type-specific quality criteria
        if self.mnemonic_type == "Story":
            prompt += """
Quality criteria:
- Should have a coherent narrative with beginning, middle, and end
- All key concepts should be woven into the narrative

"""
        elif self.mnemonic_type == "Poem":
            prompt += """
Quality criteria:
- Should have multiple complete rhyming lines (at least 4 lines)
- Each line should relate to a key concept

"""
        elif self.mnemonic_type == "Jokes":
            prompt += """
Quality criteria:
- Should have multiple complete jokes with setup and punchlines (at least 3)
- Each joke should incorporate a key concept

"""
        
        prompt += "If NO story elements were proposed at all, return empty string.\n"
        
        # Add type-specific example
        if self.mnemonic_type == "Story":
            prompt += """
Example input: "The CPU is like a brain. Memory is a notebook. Pins are like hands that turn things on/off."
Example output:
{
  "mnemonic_text": "Once upon a time, there was a Microcontroller with a Brain (CPU) that made decisions. It had a Notebook (Memory) to store instructions, and Hands (Pins) to control things by turning them ON or OFF."
}
"""
        elif self.mnemonic_type == "Poem":
            prompt += """
Example input: "CPU is the brain. Memory stores things. Pins are like hands."
Example output:
{
  "mnemonic_text": "The CPU brain thinks so fast,\\nMemory stores the recent past,\\nPins reach out like tiny hands,\\nFollowing the program's commands."
}
"""
        elif self.mnemonic_type == "Jokes":
            prompt += """
Example input: "CPU is the brain. Pins turn things on/off. Memory stores instructions."
Example output:
{
  "mnemonic_text": "Why did the CPU go to school? To get a little bit smarter!\\n\\nWhat do pins say when they're excited? I'm totally ON about this!\\n\\nWhy is memory so good at tests? It never forgets what it studied!"
}
"""
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = getattr(response, 'content', '{}')
            content = content.strip().replace('```json', '').replace('```', '')
            result = json.loads(content)
            mnemonic_text = result.get('mnemonic_text', '')
            
            if mnemonic_text:
                logging.info(f'[Mnemonic State] Extracted mnemonic ({len(mnemonic_text)} chars)')
                return True, mnemonic_text
            else:
                logging.warning('[Mnemonic State] No mnemonic text extracted from Phase 2')
                return True, ''  # Still mark as created to avoid re-running
        except Exception as e:
            logging.error(f'[Mnemonic State] Failed to extract mnemonic: {e}')
            return True, ''  # Mark as created to avoid re-running

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
        # Get the speaker of the turn being analyzed
        previous_speaker = analysis.get('speaker', 'a student')
        
        # Get mnemonic state for phase-specific instructions
        frame_memory = context['frame_memory']
        mnemonic_state = frame_memory.get(MNEMONIC_STATE_KEY, {})
        
        sections: list[PromptSection] = []

        # Section 1: Base persona and knowledge
        sections.append({
            'label': 'Marty - Persona & Knowledge',
            'content': self._get_base_prompt(),
        })

        # Section 2: Phase-specific instructions (with mnemonic state)
        sections.append({
            'label': f'Marty - Phase {phase} Instructions',
            'content': self._get_phase_instructions(phase, mnemonic_state, frame_memory),
        })

        # Section 3: Turn-taking management (if needed)
        turn_taking_content = self._get_turn_taking_instructions(
            underparticipating_students,
            suggested_next_speaker,
            consecutive_same_speaker,
            previous_speaker,
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
        base_prompt = f"""You are 'Marty,' a friendly and encouraging buddy robot facilitating a session \\
for students to create a mnemonic about '{self.topic}'.
Your response must be concise (1-3 sentences) and focus on only 1-2 concepts per turn.
IMPORTANT: Do NOT use emojis in your responses."""

        if self.target_age:
            base_prompt += f"\\nYour language must be simple and appropriate for a {self.target_age}-year-old."

        base_prompt += f"""\\nBase all your factual knowledge *exclusively* on the following material:
--- LEARNING MATERIAL ---
{self.learning_material.strip()}
-------------------------"""
        return base_prompt

    def _get_phase_instructions(self, phase: int, mnemonic_state: dict[str, Any], frame_memory: dict[str, Any]) -> str:
        """Returns the instructional part of the prompt for the current phase.

        Args:
            phase: Current session phase (1, 2, or 3)
            mnemonic_state: Dictionary containing selected_concepts, mnemonic_text, etc.
            frame_memory: Full frame memory including recall_tracking
        """
        # Add specific structural guidance based on the chosen mnemonic type.
        type_guidance = ''
        if self.mnemonic_type == 'Story':
            type_guidance = (
                'Help the students create a coherent narrative '
                'that weaves all key concepts together.'
            )
        elif self.mnemonic_type == 'Poem':
            type_guidance = (
                'Help the students write rhyming lines for a poem '
                'that each capture a key concept.'
            )
        elif self.mnemonic_type == 'Jokes':
            type_guidance = (
                'Help the students create a set of jokes where the punchline '
                'relates to a key concept.'
            )

        if phase == 1:
            return """Current Goal: Select 3-5 Key Concepts (you have ~3 minutes for this phase).
Your task is to help students SELECT which concepts they want to include in their mnemonic.

ASK students what concepts they think are important to remember. Let THEM propose concepts from what they know about the topic.

Examples:
- "What are the most important things about microcontrollers that you want to remember?"
- "Which concepts from our learning material seem trickiest to you?"
- "What would you like your story/poem/jokes to help you remember?"

ONLY if students:
- Don't know where to start → Offer 1-2 examples to get them thinking
- Suggest off-topic concepts → Gently redirect to concepts from the learning material
- Get stuck → Propose specific concepts they haven't mentioned yet

Once students have proposed 3-5 concepts, CONFIRM their selection explicitly:
"Great choices! So we're using: [list the concepts]. Ready to create our {mnemonic_type}?"

Be decisive - don't keep adding concepts once you have 3-5. Let students drive the selection."""
        elif phase == 2:
            # Get selected concepts from mnemonic_state
            selected_concepts = mnemonic_state.get('selected_concepts', [])
            concepts_str = ', '.join(selected_concepts) if selected_concepts else '[concepts from Phase 1]'
            
            # Type-specific repetition instructions
            repetition_guidance = ""
            if self.mnemonic_type == 'Story':
                repetition_guidance = 'Tell it as a narrative, not bullet points. "So far, our story goes: Once upon a time, there was [narrate what they\'ve created]... What happens next?"'
            elif self.mnemonic_type == 'Poem':
                repetition_guidance = 'Recite using this format: "So far, our poem goes: [line 1] / [line 2] / [line 3]..." What\'s the next line?'
            elif self.mnemonic_type == 'Jokes':
                repetition_guidance = 'Recite using this format: "So far, our jokes go: Joke 1: [setup]? [punchline]! Joke 2: [setup]? [punchline]!" What\'s the next joke?'
            
            return f"""Current Goal: Create the {self.mnemonic_type} Mnemonic (you have ~6 minutes for this phase).
The selected concepts are: **{concepts_str}**

Now help students BUILD their {self.mnemonic_type} using these concepts. {type_guidance}

ASK students to propose ideas for the {self.mnemonic_type}:
- "How should our {self.mnemonic_type} start?"
- "What happens next?"
- "How can we include [concept]?"

Let THEM create the {self.mnemonic_type}. Build on their ideas.

IMPORTANT: Every 2-3 student contributions, NARRATE the {self.mnemonic_type} built so far.
{repetition_guidance}
This helps students remember and build on what they've already created together.

ONLY if students:
- Don't know how to start → Suggest one opening idea as an example
- Get stuck → Prompt with questions about the next concept
- Go off-track → Gently redirect to include the selected concepts

DO NOT create the {self.mnemonic_type} for them. Your role is to facilitate THEIR creativity."""
        else:  # phase == 3
            # Get the mnemonic text from mnemonic_state
            mnemonic_text = mnemonic_state.get('mnemonic_text', '')
            recall_tracking = frame_memory.get('recall_tracking', {})
            
            # Log for debugging
            logging.info(f'[Phase 3 Instructions] mnemonic_text_length={len(mnemonic_text)}')
            
            # Check recall status
            total_attempts = sum(student_data.get('attempts', 0) for student_data in recall_tracking.values())
            contribution_type = frame_memory.get('_last_contribution_type', '')
            
            return f"""🎯 PHASE 3 - MEMORY RECALL TEST (Recall attempts: {total_attempts})
The {self.mnemonic_type} is COMPLETE: "{mnemonic_text}"

⚠️ PHASE 3 MODE - RECALL ONLY:
Creation is OVER. Testing memory is the ONLY goal now.

IF STUDENT ASKS A QUESTION (e.g., "how does X work?" or "what about Y?"):
→ DO NOT ANSWER IT
→ REDIRECT: "That's a great question, but let's first see if we can remember our {self.mnemonic_type}! [Student name], can you try reciting it?"

IF STUDENT TRIES TO ADD TO THE MNEMONIC:
→ DO NOT ACCEPT IT  
→ REDIRECT: "Our {self.mnemonic_type} is complete! Now let's practice remembering it. Who wants to try reciting it?"

IF STUDENT IS RECITING (contribution_type: 'recall_attempt'):
→ SUPPORT THEM: "Good start! What comes next?"
→ IF STUCK: "What came after [last part]?"
→ GIVE HINTS: "It starts with..."
→ AFTER COMPLETE: "Excellent! Who wants to try the whole thing?"

IF STUDENT ASKS FOR HELP (contribution_type: 'recall_question'):  
→ GIVE THE PART THEY NEED: "[missing part]"
→ THEN ASK: "Can you continue from there?"

CELEBRATE their memory work! The ONLY goal: Can they RECITE the complete {self.mnemonic_type}?"""

    def _get_turn_taking_instructions(
        self,
        underparticipating: Optional[list[str]],
        suggested_next: Optional[str],
        consecutive_same: int,
        previous_speaker: str,
    ) -> str:
        """Generates instructions for fair turn-taking and participation balance."""
        
        # Default instruction is to simply respond to the person who just spoke.
        instruction = f"\nYour response should be addressed to {previous_speaker}."

        # Determine the next speaker to invite
        next_speaker_to_invite = None
        if consecutive_same >= 2 and suggested_next:
            next_speaker_to_invite = suggested_next
        elif underparticipating:
            next_speaker_to_invite = underparticipating[0]

        # If there's an underparticipating student, create a more complex, two-part instruction.
        if next_speaker_to_invite and next_speaker_to_invite != previous_speaker:
            instruction = f"""
CRITICAL TURN MANAGEMENT:
- The student who JUST spoke is: {previous_speaker}.
- The student you MUST INVITE to speak next is: {next_speaker_to_invite}.

Your response structure MUST be:
1. FIRST: Briefly acknowledge what {previous_speaker} just said (e.g., "Great point, {previous_speaker}!").
2. SECOND: Turn to invite {next_speaker_to_invite} by asking them a direct question (e.g., "{next_speaker_to_invite}, what do you think?").

DO NOT confuse these two students."""
            logging.info(f"[Turn Management] Acknowledge {previous_speaker}, invite {next_speaker_to_invite}")
        else:
            logging.debug(f"[Turn Management] Simple instruction: address {previous_speaker}")

        return instruction

    def _get_relevance_instructions(self, off_topic_duration: int) -> str:
        """Generates an instruction to redirect if the conversation is off-topic."""
        if off_topic_duration < 2:
            return ''
        return (
            'The conversation has been off-topic for a couple of turns. '
            'Gently redirect the conversation back to the task of creating the mnemonic.'
        )

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """DEPRECATED: Validation logic has been moved to specialized frames.

        This method is now a placeholder and will always pass. The checks for
        conciseness, direct answers, and age-appropriateness are handled by
        the LanguageCheckerFrame and AnswerCheckerFrame.
        """
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
