"""A frame that facilitates a collaborative mnemonic creation session.

Exports:
    CLEANED_MESSAGE_KEY: Shared context key for cleaned user message.
    SPEAKER_KEY: Shared context key for speaker name.
    SESSION_PHASE_KEY: Shared context key for session phase.

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
        llm_client: BaseChatModel,
        target_age: Optional[int] = None,
    ):
        """Initializes the MnemonicCoCreatorFrame.

        Args:
            topic: The central theme of the mnemonic session.
            learning_material: The source text for the mnemonic.
            students: A list of student names participating in the session.
            mnemonic_type: The type of mnemonic to be created (e.g., 'Story').
            llm_client: The LLM client to use for internal analysis tasks.
            target_age: The optional target age for the students.
        """
        super().__init__()
        self.topic = topic
        self.learning_material = learning_material
        self.students = students
        self.mnemonic_type = mnemonic_type
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
        frame_memory['session_language'] = 'English'  # Default language
        frame_memory['consecutive_off_topic_turns'] = 0
        frame_memory['session_start_time'] = datetime.now().isoformat()
        # Participation and turn-taking state is now managed by the BalancedTurnsFrame
        
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

    # --- Main Slot Implementations ---

    async def analyze_input(
        self, context: FrameContext
    ) -> Optional[dict[str, Any]]:
        """Parses user input, manages session state, and tracks participation."""
        frame_memory = context['frame_memory']
        user_input = context['user_input']

        if 'turn_count' not in frame_memory:
            self._initialize_memory(frame_memory)

        # Calculate elapsed time for phase transitions.
        # If an external runner (like a simulation) has injected the time THIS turn,
        # we respect it (marked by '_elapsed_time_injected' flag).
        # Otherwise, we calculate it based on real-world time EVERY turn.
        if not frame_memory.get('_elapsed_time_injected'):
            start_time_str = frame_memory.get('session_start_time')
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
                elapsed_seconds = (datetime.now() - start_time).total_seconds()
                frame_memory['elapsed_time_minutes'] = elapsed_seconds / 60
        else:
            # Clear the injection flag so next turn recalculates unless injected again
            frame_memory['_elapsed_time_injected'] = False

        # Update turn count and session phase
        frame_memory['turn_count'] += 1
        turn = frame_memory['turn_count']
        phase = self._get_current_phase(turn, frame_memory)
        frame_memory['session_phase'] = phase

        elapsed_minutes = frame_memory.get('elapsed_time_minutes', 0)
        if phase == 3 and elapsed_minutes >= 10:
            frame_memory['_closure_ready'] = True
        elif phase < 3:
            frame_memory.pop('_closure_ready', None)
            frame_memory.pop('_closure_done', None)

        speaker, message = self._parse_user_input(user_input)

        # On the first turn, detect the language of the session
        if turn == 1 and message:
            detected_language = await self._detect_language(message)
            if detected_language:
                frame_memory['session_language'] = detected_language
                logging.info(f"[Language Detection] Session language set to: {detected_language}")

        context['shared_context'][CLEANED_MESSAGE_KEY] = message
        context['shared_context'][SPEAKER_KEY] = speaker
        context['shared_context'][SESSION_PHASE_KEY] = phase

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
            
            if contribution_type in ['mnemonic_suggestion', 'builds_on_idea']:
                current_draft = mnemonic_state.get('mnemonic_text', '')
                new_draft = await self._update_mnemonic_draft(current_draft, message, speaker)
                
                if new_draft and new_draft != current_draft:
                    mnemonic_state['mnemonic_text'] = new_draft
                    mnemonic_state['mnemonic_created'] = True
                    frame_memory[MNEMONIC_STATE_KEY] = mnemonic_state
                    logging.info(f'[Mnemonic Building] Updated draft: {new_draft}')
        
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
            'session_phase': phase,
            'off_topic_duration': frame_memory['consecutive_off_topic_turns'],
            'suggested_next_speaker': None,  # Set by balanced_turns frame later
            'consecutive_same_speaker': 0,   # Set by balanced_turns frame later
            **llm_analysis,  # understanding_level, contribution_type, is_relevant, etc.
        }

        # This allows other frames to access it without hardcoding this frame's name.
        context['shared_context'][CLEANED_MESSAGE_KEY] = message
        context['shared_context'][SPEAKER_KEY] = speaker
        context['shared_context'][SESSION_PHASE_KEY] = phase
        
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
        
        # When entering Phase 3, extract the finalized mnemonic from Marty's narrations
        # Use a separate flag to track if we've done the Phase 3 extraction
        if phase == 3 and not mnemonic_state.get('_phase3_extraction_done', False):
            logging.info('[Mnemonic State] Entering Phase 3 - extracting mnemonic from narrations')
            extracted_mnemonic = self._extract_from_last_narration(context['conversation_history'])
            mnemonic_state['_phase3_extraction_done'] = True  # Mark extraction attempted
            if extracted_mnemonic:
                mnemonic_state['mnemonic_text'] = extracted_mnemonic
                mnemonic_state['mnemonic_created'] = True
                frame_memory[MNEMONIC_STATE_KEY] = mnemonic_state
                logging.info(f'[Mnemonic State] Extracted mnemonic: {extracted_mnemonic[:100]}...')
            else:
                # Fallback: use whatever draft we have
                logging.warning('[Mnemonic State] Could not extract mnemonic from narrations, using existing draft')
                frame_memory[MNEMONIC_STATE_KEY] = mnemonic_state
        
        # Log mnemonic state for debugging
        current_mnemonic = mnemonic_state.get('mnemonic_text', '')
        if phase == 3:
            logging.info(f'[Mnemonic State] Phase 3 - mnemonic: {current_mnemonic}')
            # Track Phase 3 turn count for intro detection
            phase3_turns = frame_memory.get('_phase3_turn_count', 0) + 1
            frame_memory['_phase3_turn_count'] = phase3_turns
            logging.info(f'[Mnemonic State] Phase 3 turn: {phase3_turns}')

        self._log_event('Analysis complete.')
        return analysis_output

    def _get_current_phase(self, turn_count: int, frame_memory: dict[str, Any]) -> int:
        """Determines the current session phase based on elapsed time.
        
        Phase transitions are strictly time-based:
        - Phase 1: 0-3 minutes (Concept Selection)
        - Phase 2: 3-7 minutes (Mnemonic Creation)
        - Phase 3: 7+ minutes (Recall Practice)
        """
        elapsed_time = frame_memory.get('elapsed_time_minutes', 0)
        
        # Phase 3: After 7 minutes
        if elapsed_time >= 7:
            return 3
        # Phase 2: After 3 minutes
        elif elapsed_time >= 3:
            return 2
        # Phase 1: First 3 minutes
        else:
            return 1
    
    async def _update_mnemonic_draft(self, current_draft: str, message: str, speaker: str) -> str:
        """Uses an LLM to intelligently integrate a new idea into the mnemonic draft."""
        
        if not current_draft:
            draft_section = "The draft is currently empty."
        else:
            draft_section = f"CURRENT DRAFT:\n{current_draft}"

        prompt = f"""You are a collaborative story editor. Your task is to integrate a student's new idea into the current draft of a "{self.mnemonic_type}" mnemonic about "{self.topic}".

{draft_section}

STUDENT'S NEW IDEA:
"{speaker}: {message}"

TASK:
Your task is to act as a text editor and integrate the student's new idea into the current draft.
- If the draft is empty, the student's idea is the new draft.
- If the idea is an addition, append it to the end of the current draft.
- If the idea seems to be a correction, replace the relevant part of the draft.
- CRITICAL: Do NOT add any extra words, sentences, or explanations. Your goal is only to integrate the student's exact contribution.
- CRITICAL: Do NOT include the speaker's name (e.g., "Blue:") or any conversational filler in the final draft. The output should be ONLY the mnemonic text itself.

NEW DRAFT:"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            new_draft = getattr(response, 'content', '').strip()
            
            if new_draft:
                logging.info(f'[Mnemonic Update] Updated draft with input from {speaker}.')
                return new_draft
            else:
                return current_draft # Return old draft if LLM returns nothing
        except Exception as e:
            logging.error(f'[Mnemonic Update] Error updating draft: {e}')
            return current_draft # Return old draft on error
    
    def _extract_from_last_narration(self, conversation_history: list[dict]) -> str:
        """Extracts the mnemonic from Marty's LAST narration in Phase 2.
        
        Looks for Marty's most recent "So far, our story goes:" or similar pattern
        and extracts the complete mnemonic text after it.
        """
        # Search backwards through conversation for Marty's narrations
        # Use type-specific patterns for better matching
        mnemonic_type_lower = self.mnemonic_type.lower()
        
        if mnemonic_type_lower == 'story':
            narration_patterns = [
                r'So far,? our story (?:goes?|is):\s*(.*)',
                r'(?:Our|The) story (?:now is|so far):\s*(.*)',
                r'Here\'?s? (?:the|our) story so far:\s*(.*)',
                r'story (?:now|goes):\s*["\']?(.*)',
            ]
        elif mnemonic_type_lower == 'poem':
            narration_patterns = [
                r'So far,? our poem (?:goes?|is):\s*(.*)',
                r'(?:Our|The) poem (?:now is|lines now are|so far):\s*(.*)',
                r'Our poem lines (?:now are|are):\s*(.*)',
                r'Here\'?s? (?:the|our) poem so far:\s*(.*)',
                r'poem (?:now|lines):\s*["\']?(.*)',
            ]
        else:  # jokes
            narration_patterns = [
                r'So far,? our jokes? (?:go|are|is):\s*(.*)',
                r'(?:Our|The) jokes? (?:now are|so far):\s*(.*)',
                r'Here\'?s? (?:the|our) jokes? so far:\s*(.*)',
                r'jokes? (?:now|so far):\s*["\']?(.*)',
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
        off_topic_duration = analysis.get('off_topic_duration', 0)
        # Get the speaker of the turn being analyzed
        previous_speaker = analysis.get('speaker', 'a student')
        
        # Get turn-taking info from balanced_turns frame
        from backend.frames.balanced_turns import SUGGESTED_NEXT_SPEAKER_KEY, CONSECUTIVE_SAME_SPEAKER_KEY
        suggested_next_speaker = context['shared_context'].get(SUGGESTED_NEXT_SPEAKER_KEY)
        consecutive_same_speaker = context['shared_context'].get(CONSECUTIVE_SAME_SPEAKER_KEY, 0)

        # Get mnemonic state for phase-specific instructions
        # Note: marty writes to root of frame_memory, not under self.name
        frame_memory = context['frame_memory']
        mnemonic_state = frame_memory.get(MNEMONIC_STATE_KEY, {})
        
        sections: list[PromptSection] = []

        # Section 1: Base persona and knowledge
        sections.append({
            'label': 'Marty - Persona & Knowledge',
            'content': self._get_base_prompt(frame_memory),
        })

        # Section 2: Phase-specific instructions (with mnemonic state)
        sections.append({
            'label': f'Marty - Phase {phase} Instructions',
            'content': self._get_phase_instructions(phase, mnemonic_state, frame_memory),
        })

        # Section 3: Turn-taking instructions
        turn_taking_content = self._get_turn_taking_instructions(
            previous_speaker, suggested_next_speaker, consecutive_same_speaker
        )
        if turn_taking_content:
            sections.append({
                'label': 'Marty - Turn-Taking',
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

    def _get_base_prompt(self, frame_memory: dict[str, Any]) -> str:
        """Returns the static, core part of the system prompt."""
        session_language = frame_memory.get('session_language', 'English')
        
        base_prompt = f"""You are 'Marty,' a friendly and encouraging buddy robot facilitating a session \\
for students to create a mnemonic about '{self.topic}'.
Your response must be concise (1-3 sentences) and focus on only 1-2 concepts per turn.
CRITICAL: You MUST write all your responses in {session_language}.
IMPORTANT: Do NOT use emojis in your responses."""

        if self.target_age:
            base_prompt += f"\\nYour language must be simple and appropriate for a {self.target_age}-year-old."

        base_prompt += f"""\nBase all your factual knowledge *exclusively* on the following material:
--- LEARNING MATERIAL ---
{self.learning_material.strip()}
-------------------------"""
        return base_prompt

    def _get_phase_instructions(self, phase: int, mnemonic_state: dict[str, Any], frame_memory: dict[str, Any]) -> str:
        """Returns the instructional part of the prompt for the current phase."""
        if phase == 1:
            return self._get_phase_1_instructions()
        elif phase == 2:
            return self._get_phase_2_instructions(mnemonic_state)
        else:  # phase == 3
            return self._get_phase_3_instructions(mnemonic_state, frame_memory)

    def _get_phase_1_instructions(self) -> str:
        """Returns the prompt instructions for Phase 1: Concept Selection."""
        return f"""Current Goal: Select 3-5 Key Concepts (you have ~3 minutes for this phase).
Your task is to help students SELECT which concepts they think are important to remember. Let THEM propose concepts.

CRITICAL RULES:
1. DO NOT PROPOSE, SUGGEST, OR LIST ANY CONCEPTS YOURSELF. Not even as examples or as multiple-choice questions.
2. Your ONLY job is to ASK students an open-ended question to let THEM come up with the concepts first.
3. LANGUAGE: If a student speaks in a language other than English (e.g., German), you MUST respond in that same language.

GOOD Examples of what to ask:
- "What are the most important things about microcontrollers that you want to remember?"
- "Which concepts from our learning material seem trickiest to you?"
- "What would you like your {self.mnemonic_type} to help you remember?"

BAD Examples (DO NOT DO THIS):
- BAD Example 1: "Nice idea! Let's start with this concept: the ESP32 is Marty's brain."
- BAD Example 2: "That’s a great start! Which concepts feel trickiest: (a) what a microcontroller is, or (b) how pins work?"

IF a student is stuck OR explicitly says they do not understand a concept (e.g., "I don't get it" or "Ich verstehe nicht"):
1. FIRST, ask another student if they can help (e.g., "[Other Student], can you try to explain it in your own words?").
2. IF that doesn't work, then YOU can ask a focused, diagnostic question to break down their confusion (e.g., "Thanks for letting me know. To help, what specific part about it is most confusing?").
3. ONLY if everyone is struggling after both steps, you can then offer ONE small example to get them thinking.

Once students have proposed and agreed on 3-5 concepts, CONFIRM the final list:
"Perfect! So our concepts are: [list the concepts]. Ready to start building our {self.mnemonic_type}?"""

    def _get_phase_2_instructions(self, mnemonic_state: dict[str, Any]) -> str:
        """Returns the prompt instructions for Phase 2: Mnemonic Creation."""
        selected_concepts = mnemonic_state.get('selected_concepts', [])
        concepts_str = ', '.join(selected_concepts) if selected_concepts else '[concepts from Phase 1]'
        
        repetition_guidance = ""
        if self.mnemonic_type == 'Story':
            repetition_guidance = 'Tell it as a narrative. "So far, our story goes: [narrate the draft]... What happens next?"'
        elif self.mnemonic_type == 'Poem':
            repetition_guidance = 'Recite the poem so far. "Our poem so far: [line 1] / [line 2]..." What\'s the next line?'
        elif self.mnemonic_type == 'Jokes':
            repetition_guidance = 'Recite the jokes. "Our jokes so far: Joke 1: [...] Joke 2: [...]" What\'s the next joke?'

        return f"""Current Goal: Create the {self.mnemonic_type} Mnemonic (you have ~6 minutes for this phase).
The selected concepts are: **{concepts_str}**

Your task is to help students BUILD their {self.mnemonic_type} using these concepts.
ASK students to propose ideas BY NAME (always acknowledge who just spoke, then invite the next student):
- "[Student who spoke], great idea! [Next student], how should our {self.mnemonic_type} start?"
- "Nice, [Student]! [Next student], how can we include [concept]?"

IF a student is stuck:
1. FIRST, ask another student for their ideas (e.g., "[Other Student], how do you think we can continue the story?").
2. ONLY if all students are stuck, suggest one opening idea as an example.

IMPORTANT: Every 2-3 student contributions, NARRATE the {self.mnemonic_type} built so far.
{repetition_guidance}
This helps students remember and build on what they've already created.
DO NOT create the {self.mnemonic_type} for them. Your role is to facilitate THEIR creativity.

TURN-TAKING REMINDER: In EVERY response, you MUST address the student who just spoke by name AND invite a different student to contribute next."""

    def _get_phase_3_instructions(self, mnemonic_state: dict[str, Any], frame_memory: dict[str, Any]) -> str:
        """Returns the prompt instructions for Phase 3: Recall Practice."""
        mnemonic_text = mnemonic_state.get('mnemonic_text', '')
        # Recall tracking is now in marty's namespaced memory
        recall_tracking = frame_memory.get('recall_tracking', {})
        total_attempts = sum(student_data.get('attempts', 0) for student_data in recall_tracking.values())
        
        # Check if this is the first turn of Phase 3
        phase3_turn_count = frame_memory.get('_phase3_turn_count', 1)
        is_first_phase3_turn = phase3_turn_count == 1

        closure_ready = frame_memory.get('_closure_ready', False)
        closure_done = frame_memory.get('_closure_done', False)
        elapsed_minutes = frame_memory.get('elapsed_time_minutes', 0)
        selected_concepts = mnemonic_state.get('selected_concepts', [])

        if closure_ready and not closure_done:
            frame_memory['_closure_done'] = True
            concepts_summary = ', '.join(selected_concepts) if selected_concepts else 'the key ideas you discussed'
            if mnemonic_text:
                mnemonic_summary = f'The {self.mnemonic_type.lower()} you built:\n"{mnemonic_text}"'
            else:
                mnemonic_summary = f'You outlined how your {self.mnemonic_type.lower()} should work, even if it is not fully written out.'
            return f"""🎉 SESSION WRAP-UP (Time limit reached)
Approximately {elapsed_minutes:.1f} minutes have passed, so it is time to close the session warmly.

YOUR FINAL RESPONSE MUST:
1. Acknowledge the student who just spoke and mention that our 10-minute session is over.
2. Celebrate what the group accomplished (concepts chosen: {concepts_summary}; {mnemonic_summary}).
3. Encourage them to keep practicing together or on their own.
4. Offer a friendly goodbye (e.g., "Thanks for the great teamwork—see you next time!").
5. Do NOT invite another student to speak; this is the closing message."""
        
        # Check if we have a valid mnemonic (at least 20 chars and doesn't look like incomplete input)
        has_valid_mnemonic = (
            mnemonic_text 
            and len(mnemonic_text) > 20 
            and ':' not in mnemonic_text[:30]  # Avoid "Blue: ..." student input fragments
        )
        
        # Handle case where no proper mnemonic was created
        if not has_valid_mnemonic:
            return f"""🎯 PHASE 3 - WRAP UP

⚠️ NO COMPLETE {self.mnemonic_type.upper()} WAS CREATED
It looks like we ran out of time before finishing our {self.mnemonic_type}.

YOUR TASK:
1. Acknowledge this warmly: "[Student who spoke], it looks like we got a bit stuck on our {self.mnemonic_type}!"
2. Summarize what was accomplished: "We did talk about some great concepts like [mention 1-2 concepts discussed]."
3. Encourage them: "Sometimes the best ideas take time. What did you learn about microcontrollers today?"
4. Invite reflection BY NAME: "[Next student], what was your favorite part of our discussion?"

DO NOT pretend there's a poem to recite. Be honest and supportive.

TURN-TAKING REMINDER: In EVERY response, you MUST address the student who just spoke by name AND invite a different student to contribute next."""

        # First turn of Phase 3: Marty should recite the poem first
        if is_first_phase3_turn:
            return f"""🎯 PHASE 3 - MEMORY RECALL TEST (Starting!)
The {self.mnemonic_type} is COMPLETE!

YOUR FIRST TASK: RECITE THE FULL {self.mnemonic_type.upper()} TO THE STUDENTS!
Start your response with: "Great work everyone! Here's the {self.mnemonic_type} we created together:"
Then recite it clearly:
"{mnemonic_text}"

After reciting, invite a student BY NAME to try: "[Student], do you want to try reciting it from memory? I'll help if you get stuck!"

This gives students a clear reminder before asking them to recall.

TURN-TAKING REMINDER: Address the student who just spoke by name AND invite a different student to try reciting."""

        # Subsequent turns of Phase 3
        return f"""🎯 PHASE 3 - MEMORY RECALL TEST (Recall attempts: {total_attempts})
The {self.mnemonic_type} is: "{mnemonic_text}"

⚠️ RECALL ONLY MODE:
Creation is OVER. Testing memory is the ONLY goal now.

IF a student asks a question or tries to add to the mnemonic:
→ DO NOT ANSWER or ACCEPT IT.
→ REDIRECT BY NAME: "[Student who spoke], that's a great thought! [Next student], can you try reciting our {self.mnemonic_type} for us?"

IF a student is reciting and gets stuck:
1. FIRST, ask another student BY NAME if they can help (e.g., "[Student], nice try! [Other Student], can you help with the next part?").
2. ONLY if all students are stuck, GIVE HINTS: "What came after [last part]?" or "It starts with..."

CELEBRATE their memory work! The ONLY goal: Can they RECITE the complete {self.mnemonic_type}?

TURN-TAKING REMINDER: In EVERY response, you MUST address the student who just spoke by name AND invite a different student to contribute next."""

    async def _detect_language(self, message: str) -> str:
        """Uses an LLM to detect the language of a given text."""
        prompt = f'''What language is this text written in? Respond with ONLY the name of the language in English (e.g., "German", "English", "French").

Text: "{message}"

Language:'''
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            language = getattr(response, 'content', '').strip()
            # Basic validation
            if language and len(language) < 20 and all(c.isalpha() or c.isspace() for c in language):
                return language
        except Exception as e:
            logging.error(f'[Language Detection] Failed to detect language: {e}')
        return 'English' # Default to English on failure

    def _get_turn_taking_instructions(
        self,
        previous_speaker: str,
        suggested_next_speaker: Optional[str],
        consecutive_same_speaker: int,
    ) -> str:
        """Generates turn-taking instructions using suggested_next_speaker from balanced_turns."""
        if suggested_next_speaker and suggested_next_speaker != previous_speaker:
            return (
                f"To ensure balanced participation, after acknowledging {previous_speaker}, "
                f"please invite {suggested_next_speaker} to contribute next."
            )
        return ''

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
