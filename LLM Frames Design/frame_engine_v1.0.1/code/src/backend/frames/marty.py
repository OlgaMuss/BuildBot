"""A frame that facilitates a collaborative mnemonic creation session."""
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from backend.frame_engine.core import (
    Frame,
    FrameContext,
    ValidationAction,
    ValidationResult,
)
from langchain_core.language_models.chat_models import BaseChatModel

# --- Constants for Clarity (Avoid Magic Strings) ---
_USER_INPUT_PATTERN = re.compile(r"\[\d{2}:\d{2}:\d{2}\]\s*(\w+):\s*(.*)")
_SESSION_LOG_DIR = Path("sessions")
_SESSION_LOG_INIT_MSG = "New session started."
_SESSION_LOG_SAVE_MSG = "Session log saved to {}"

_ANALYSIS_PROMPT_TEMPLATE = """
You are an expert AI assistant analyzing a single turn in a collaborative learning session.
Your goal is to provide a structured analysis of the student's message.
Your output MUST be a valid JSON object. Do not add any text before or after the JSON.

**CONTEXT:**
- Topic: {topic}
- Mnemonic Type: {mnemonic_type}
- Current Turn: {turn_count}
- Session Phase: {session_phase}
- Learning Material (Key Concepts):
{learning_material}
- Conversation History:
{history}

**STUDENT MESSAGE:**
"{speaker}: {message}"

**ANALYSIS TASK:**
Analyze the student's message and provide the following in a JSON object:
1.  `contribution_type`: Classify the message. Choose one: "mnemonic_suggestion", "knowledge_statement", "question", "builds_on_idea", "off_topic".
2.  `concepts_understood`: A list of concept names from the learning material that the student demonstrates understanding of in this message. Empty list if none.
3.  `concepts_confused`: A list of concept names from the learning material that the student seems confused about or gets wrong. Empty list if none.
4.  `concepts_mentioned_for_mnemonic`: A list of concepts the student explicitly suggests including in the mnemonic. Empty list if none.
5.  `is_relevant`: A boolean (`true` or `false`) indicating if the message is relevant to the topic or task.
6.  `mnemonic_progress`: A brief, one-sentence summary of the current state of the co-created mnemonic.
7.  `summary`: A one-sentence summary of the student's message.
8.  `current_mnemonic_draft`: The exact text of the mnemonic (story, acronym, or poem) as it currently stands based on the conversation so far. If no mnemonic text has been proposed yet, use null or empty string.

**JSON OUTPUT EXAMPLE:**
{{
  "contribution_type": "knowledge_statement",
  "concepts_understood": ["CPU", "memory"],
  "concepts_confused": [],
  "concepts_mentioned_for_mnemonic": ["CPU", "memory"],
  "is_relevant": true,
  "mnemonic_progress": "The group is identifying which components to include in their story.",
  "summary": "The student explains that microcontrollers have a CPU and memory.",
  "current_mnemonic_draft": "Mister mean bought a drone..."
}}
"""


class MnemonicCoCreatorFrame(Frame):
    """A frame that guides students to collaboratively create a mnemonic."""

    def __init__(
        self,
        topic: str,
        learning_material: str,
        students: List[str],
        mnemonic_type: str,
        phase_config: Dict[str, int],
        llm_client: BaseChatModel,
    ):
        """Initializes the MnemonicCoCreatorFrame.

        Args:
            topic: The central theme of the mnemonic session.
            learning_material: The source text for the mnemonic.
            students: A list of student names participating in the session.
            mnemonic_type: The type of mnemonic to be created (e.g., 'Story').
            phase_config: A dictionary defining the time boundaries in minutes for each phase.
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
        self.session_log: list[dict] = []

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return "mnemonic_co_creator_marty"

    # --- Helper Methods for Analyze Input (Single Responsibility) ---

    def _initialize_memory(self, frame_memory: Dict[str, Any]) -> None:
        """Sets up the initial state in `frame_memory` for a new session."""
        frame_memory["turn_count"] = 0
        frame_memory["start_time"] = datetime.now().isoformat()
        frame_memory["phase_1_start"] = datetime.now().isoformat()
        frame_memory["session_phase"] = 1
        frame_memory["session_language"] = "German"  # Default to German as per requirement
        frame_memory["turn_queue"] = list(self.students)  # Initialize the turn queue
        frame_memory["consecutive_off_topic_turns"] = 0
        frame_memory["current_mnemonic"] = ""  # Initialize current mnemonic
        frame_memory["participation"] = {
            student: {
                "contribution_count": 0,
                "concepts_understood": set(),  # Track which concepts this student understands
                "concepts_confused": set(),  # Track which concepts this student is confused about
                "concepts_history": []  # History of concept understanding per turn
            }
            for student in self.students
        }
        self._log_event(_SESSION_LOG_INIT_MSG)
        logging.info("New session started. ID: %s", self.session_id)

    def _parse_user_input(self, user_input: str) -> tuple[str, str]:
        """Extracts the speaker's name and their message from the raw input string."""
        match = _USER_INPUT_PATTERN.match(user_input)
        if match:
            return match.group(1), match.group(2).strip()
        # Fallback for unformatted input (e.g., from Streamlit)
        if ":" in user_input:
            speaker, message = user_input.split(":", 1)
            if speaker in self.students:
                return speaker, message.strip()
        return "Unknown", user_input

    def _update_turn_queue(self, frame_memory: Dict[str, Any], speaker: str) -> None:
        """Moves the current speaker to the end of the turn queue."""
        if speaker in frame_memory.get("turn_queue", []):
            frame_memory["turn_queue"].remove(speaker)
            frame_memory["turn_queue"].append(speaker)

    def _update_participation(
        self, frame_memory: Dict[str, Any], speaker: str
    ) -> Optional[str]:
        """Tracks student contributions and identifies the next student to speak."""
        if speaker in frame_memory["participation"]:
            frame_memory["participation"][speaker]["contribution_count"] += 1

        self._update_turn_queue(frame_memory, speaker)

        # The next person to invite is the one at the front of the queue,
        # but only if they are also underparticipating.
        counts = [
            data["contribution_count"]
            for data in frame_memory["participation"].values()
        ]
        
        logging.debug(f"[Participation] Speaker: {speaker}, Counts: {counts}, Turn Queue: {frame_memory.get('turn_queue', [])}")
        
        if not counts or max(counts) < 2:
            logging.debug(f"[Participation] Not enough turns yet (max: {max(counts) if counts else 0})")
            return None # Not enough turns yet to determine participation imbalance

        min_contributions = min(counts)
        max_contributions = max(counts)
        gap = max_contributions - min_contributions
        
        logging.debug(f"[Participation] Min: {min_contributions}, Max: {max_contributions}, Gap: {gap}")
        
        if gap < 2:
            logging.debug(f"[Participation] Participation is balanced (gap < 2)")
            return None # Participation is balanced

        for student in frame_memory.get("turn_queue", []):
            student_count = frame_memory["participation"][student]["contribution_count"]
            logging.debug(f"[Participation] Checking {student}: count={student_count}, min={min_contributions}")
            if student_count == min_contributions:
                logging.info(f"[Participation] Inviting underparticipating student: {student}")
                return student
        
        logging.debug(f"[Participation] No underparticipating student found in queue")
        return None

    # --- Main Slot Implementations ---

    async def analyze_input(
        self, context: FrameContext
    ) -> Optional[Dict[str, Any]]:
        """Parses user input, manages session state, and tracks participation."""
        frame_memory = context["frame_memory"]
        user_input = context["user_input"]

        if "turn_count" not in frame_memory:
            self._initialize_memory(frame_memory)

        # Update turn count and session phase
        frame_memory["turn_count"] += 1
        turn = frame_memory["turn_count"]
        start_time = datetime.fromisoformat(frame_memory["start_time"])
        old_phase = frame_memory["session_phase"]
        phase = self._get_current_phase(start_time)
        
        # Track phase transitions with timestamps
        if phase != old_phase:
            phase_key = f"phase_{phase}_start"
            frame_memory[phase_key] = datetime.now().isoformat()
            logging.info(f"[Phase Transition] Moving from Phase {old_phase} to Phase {phase}")
        
        frame_memory["session_phase"] = phase

        speaker, message = self._parse_user_input(user_input)
        next_speaker = self._update_participation(frame_memory, speaker)

        # On the first turn, detect the language of the input.
        if turn == 1:
            detected_language = await self._detect_language(message)
            frame_memory["session_language"] = detected_language

        # Perform the deep analysis using an LLM call.
        llm_analysis = await self._run_llm_analysis(
            context, speaker, message, turn, phase
        )

        # Store the concept understanding for the current speaker.
        if speaker in frame_memory["participation"]:
            concepts_understood = set(llm_analysis.get("concepts_understood", []))
            concepts_confused = set(llm_analysis.get("concepts_confused", []))
            
            # Update cumulative understanding
            frame_memory["participation"][speaker]["concepts_understood"].update(concepts_understood)
            frame_memory["participation"][speaker]["concepts_confused"].update(concepts_confused)
            # Remove from confused if now understood
            frame_memory["participation"][speaker]["concepts_confused"] -= concepts_understood
            
            # Store history
            frame_memory["participation"][speaker]["concepts_history"].append(
                {
                    "turn": turn,
                    "concepts_understood": list(concepts_understood),
                    "concepts_confused": list(concepts_confused),
                    "concepts_for_mnemonic": llm_analysis.get("concepts_mentioned_for_mnemonic", []),
                }
            )

        # Track off-topic duration
        if llm_analysis.get("is_relevant") is False:
            frame_memory["consecutive_off_topic_turns"] += 1
        else:
            frame_memory["consecutive_off_topic_turns"] = 0

        # Update current mnemonic if a new draft is provided
        current_draft = llm_analysis.get("current_mnemonic_draft")
        if current_draft:
            frame_memory["current_mnemonic"] = current_draft

        # Consolidate all findings for shared_context.
        analysis_output = {
            "turn_count": turn,
            "speaker": speaker,
            "message": message,
            "participation": frame_memory["participation"],
            "session_phase": phase,
            "underparticipating_students": next_speaker, # This key now holds the next speaker
            "off_topic_duration": frame_memory["consecutive_off_topic_turns"],
            **llm_analysis,  # Add the rich analysis from the LLM
        }

        self._log_event("Analysis complete.", analysis_output)
        return analysis_output

    def _get_current_phase(self, start_time: datetime) -> int:
        """Determines the current session phase based on elapsed time."""
        elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60
        if elapsed_minutes <= self.phases.get("phase_1_end_minutes", 2):
            return 1
        elif elapsed_minutes <= self.phases.get("phase_2_end_minutes", 8):
            return 2
        return 3

    async def _run_llm_analysis(
        self, context: FrameContext, speaker: str, message: str, turn: int, phase: int
    ) -> Dict[str, Any]:
        """Uses an LLM to perform a deep analysis of the user's input.

        This internal method is the core of the frame's intelligence. It
        constructs a specialized prompt to ask an LLM to classify the user's
        contribution, assess their understanding of specific concepts, and check for relevance.
        This structured data is then used by the `shape_prompt` slot to
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
        history_str = json.dumps(context["conversation_history"], indent=2)
        prompt = _ANALYSIS_PROMPT_TEMPLATE.format(
            topic=self.topic,
            mnemonic_type=self.mnemonic_type,
            turn_count=turn,
            session_phase=phase,
            learning_material=self.learning_material.strip(),
            history=history_str,
            speaker=speaker,
            message=message,
        )

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            analysis_json = getattr(response, "content", "{}")
            # Clean the response to ensure it's valid JSON
            analysis_json = analysis_json.strip().replace("```json", "").replace("```", "")
            return json.loads(analysis_json)
        except (json.JSONDecodeError, Exception) as e:
            logging.error("Failed to parse LLM analysis response: %s", e)
            # Return a default, safe structure on failure
            return {
                "contribution_type": "unknown",
                "concepts_understood": [],
                "concepts_confused": [],
                "concepts_mentioned_for_mnemonic": [],
                "is_relevant": True,
                "mnemonic_progress": "Analysis failed.",
                "summary": "Analysis failed.",
                "current_mnemonic_draft": ""
            }

    async def _detect_language(self, text: str) -> str:
        """Detects the language of the given text."""
        prompt = f"""
        Analyze the following text and identify its primary language.
        Respond with only the name of the language (e.g., "German", "English").

        Text: "{text}"
        """
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            language = getattr(response, "content", "German").strip()
            logging.info("Detected language: %s", language)
            return language
        except Exception as e:
            logging.error("Language detection failed: %s", e)
            return "German"  # Default to German on failure

    async def shape_prompt(self, context: FrameContext) -> str:
        """Constructs the system prompt based on the current session phase."""
        analysis = context["shared_context"][self.name]
        phase = analysis.get("session_phase", 1)
        
        # Use clearer variable names
        previous_speaker = analysis.get("speaker", "a student")
        next_speaker = analysis.get("underparticipating_students") # This key now holds the next speaker
        
        # Get concept understanding from frame memory
        frame_memory = context["frame_memory"]
        participation = frame_memory.get("participation", {})
        
        concepts_understood = analysis.get("concepts_understood", [])
        concepts_confused = analysis.get("concepts_confused", [])
        off_topic_duration = analysis.get("off_topic_duration", 0)

        logging.debug(f"[ShapePrompt] Previous speaker: {previous_speaker}, Next speaker: {next_speaker}")
        logging.debug(f"[ShapePrompt] Concepts understood: {concepts_understood}, Concepts confused: {concepts_confused}")

        # Remove speaker from base prompt call
        base_prompt = self._get_base_prompt(context)
        phase_instructions = self._get_phase_instructions(
            phase, concepts_understood, concepts_confused, participation
        )
        
        # Pass both speakers to participation instructions
        participation_instructions = self._get_participation_instructions(
            previous_speaker, next_speaker
        )
        
        relevance_instructions = self._get_relevance_instructions(off_topic_duration)

        return (
            base_prompt
            + phase_instructions
            + participation_instructions
            + relevance_instructions
        )

    def _get_base_prompt(self, context: FrameContext) -> str:
        """Returns the static, core part of the system prompt."""
        language = context["frame_memory"].get("session_language", "German")
        student_list = ", ".join(self.students)
        return f"""You are 'Marty,' a friendly and encouraging buddy robot facilitating a session for students in Germany to create a mnemonic about '{self.topic}'.
The students participating are: {student_list}. You must only use these names when addressing students.
The students are speaking {language}. Your response MUST be in {language}.
Your response must be concise (1-3 sentences) and focus on only 1-2 concepts per turn.
Base all your factual knowledge *exclusively* on the following material:
--- LEARNING MATERIAL ---
{self.learning_material.strip()}
-------------------------
"""

    def _get_phase_instructions(
        self, 
        phase: int, 
        concepts_understood: List[str],
        concepts_confused: List[str],
        participation: Dict[str, Any]
    ) -> str:
        """Returns the instructional part of the prompt for the current phase."""
        
        # Add specific structural guidance based on the chosen mnemonic type.
        type_guidance = ""
        if self.mnemonic_type == "Story":
            type_guidance = "Help the students create a coherent narrative that weaves all key concepts together."
        elif self.mnemonic_type == "Acronym":
            type_guidance = "Help the students build an acronym where each letter stands for a key concept."
        elif self.mnemonic_type == "Song":
            type_guidance = "Help the students write rhyming lines for a song that each capture a key concept."
        
        # Aggregate all concepts across students
        all_understood = set()
        all_confused = set()
        for student_data in participation.values():
            all_understood.update(student_data.get("concepts_understood", set()))
            all_confused.update(student_data.get("concepts_confused", set()))
        
        # Create guidance based on concept understanding
        concept_guidance = ""
        if concepts_confused:
            concept_guidance = f"The student seems confused about: {', '.join(concepts_confused)}. Address these misconceptions gently."
        elif all_understood:
            concept_guidance = f"The group understands: {', '.join(all_understood)}. Focus on concepts they don't fully understand yet."

        if phase == 1:
            return f"""
Current Goal: Identify Knowledge Gaps and What Needs Remembering.
Your primary task is to identify what the students don't fully understand about '{self.topic}' and which concepts they need a mnemonic to remember. 
- Focus on concepts they find difficult or don't know yet
- Skip concepts they already understand well  
Ask open questions that help students identify what they know and what's unclear. 
{concept_guidance if concept_guidance else "Explore their understanding of the key concepts."}
"""
        elif phase == 2:
            return f"""
Current Goal: Create the Mnemonic.
Your task is to guide the students to create a '{self.mnemonic_type}' mnemonic for the concepts they need to remember.
{type_guidance}
Focus on concepts that are difficult for them or that they're still learning. Don't include concepts they already know well.
{concept_guidance if concept_guidance else ""}
"""
        return f"""
Current Goal: Memorization & Practice.
Your task is to test the students' recall of the mnemonic. Ask them to recite parts or fill in the blanks. 
Encourage them to help each other remember. Reinforce the connection between the mnemonic and the actual concepts.
{type_guidance}
{concept_guidance if concept_guidance else ""}
"""
    
    def _get_participation_instructions(self, previous_speaker: str, next_speaker: Optional[str]) -> str:
        """Generates instructions for acknowledging the previous speaker and inviting the next."""
        
        # Default instruction is to simply respond to the person who just spoke.
        instruction = f"\nYour response should be addressed to {previous_speaker}."

        # If there's an underparticipating student, create a more complex, two-part instruction.
        if next_speaker and next_speaker != previous_speaker:
            instruction = f"""
CRITICAL TURN MANAGEMENT:
- The student who JUST spoke (in the message you're responding to) is: {previous_speaker}
- The student you need to INVITE to speak next is: {next_speaker}

Your response structure MUST be:
1. FIRST: Acknowledge what {previous_speaker} just said (e.g., "Great thinking, {previous_speaker}!" or "I like that idea, {previous_speaker}!").
2. SECOND: Turn to invite {next_speaker} by asking them a question (e.g., "{next_speaker}, what are your thoughts on this?" or "What do you think, {next_speaker}?").

DO NOT confuse these two students. DO NOT address your acknowledgment to {next_speaker}."""
            logging.info(f"[Participation Instructions] Generated two-part instruction: acknowledge {previous_speaker}, invite {next_speaker}")
        else:
            logging.debug(f"[Participation Instructions] Simple instruction: address {previous_speaker} (next_speaker={next_speaker})")

        return instruction

    def _get_relevance_instructions(self, off_topic_duration: int) -> str:
        """Generates an instruction to redirect if the conversation is off-topic."""
        if off_topic_duration < 2:
            return ""
        return "\nThe conversation has been off-topic for a couple of turns. Gently redirect the conversation back to the task of creating the mnemonic."

    def _validate_student_names(
        self, response: str, previous_speaker: str, next_speaker: Optional[str]
    ) -> Optional[str]:
        """Validates that the response uses the correct student names.
        
        Args:
            response: The LLM's draft response
            previous_speaker: The student who just spoke
            next_speaker: The student who should be invited (if any)
            
        Returns:
            An error message if validation fails, None if validation passes
        """
        # Get all student names from the response
        mentioned_students = [s for s in self.students if s in response]
        
        logging.debug(f"[Name Validation] Previous: {previous_speaker}, Next: {next_speaker}, Mentioned: {mentioned_students}")
        
        # Case 1: Two-part response (acknowledge previous, invite next)
        if next_speaker and next_speaker != previous_speaker:
            # 1. Check for extraneous names (not prev or next speaker)
            miscalled_students = [s for s in mentioned_students if s not in [previous_speaker, next_speaker]]
            if miscalled_students:
                return f"CRITICAL ERROR: You mentioned {', '.join(miscalled_students)}, which is incorrect. In this turn, you should only interact with {previous_speaker} and {next_speaker}."

            # Split response to analyze acknowledgment (first half) and invitation (second half)
            midpoint = len(response) // 2
            first_half = response[:midpoint]
            second_half = response[midpoint:]

            # 2. Explicitly check for a direct swap of roles
            prev_in_second = previous_speaker in second_half
            next_in_first = next_speaker in first_half
            
            if prev_in_second and next_in_first:
                return f"CRITICAL ERROR: You seem to have swapped the students. You must FIRST acknowledge {previous_speaker}, and THEN invite {next_speaker}."

            # 3. Check for partial errors (one student mentioned in the wrong half)
            if next_in_first:
                return f"CRITICAL ERROR: The first part of your response should acknowledge {previous_speaker}, but it seems to mention {next_speaker} instead."

            if prev_in_second:
                return f"CRITICAL ERROR: The second part of your response should invite {next_speaker}, but it seems to mention {previous_speaker} instead."
        
        # Case 2: Simple response (just address the previous speaker)
        else:
            # ONLY check if wrong students are mentioned - it's OK to not mention names
            wrong_students = [s for s in mentioned_students if s != previous_speaker]
            
            if wrong_students:
                return f"CRITICAL ERROR: You addressed {', '.join(wrong_students)} but the student who just spoke is {previous_speaker}. You MUST NOT address {', '.join(wrong_students)}."
        
        # If we reached here, no wrong names were used
        if mentioned_students:
            logging.info(f"[Name Validation] PASSED - Mentioned: {mentioned_students}, Expected context: {previous_speaker}" + 
                        (f" (inviting {next_speaker})" if next_speaker else ""))
        else:
            logging.info(f"[Name Validation] PASSED - No names mentioned (OK)")
        return None

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Validates the LLM's response for correct student addressing."""
        llm_response = context["llm_draft_response"]
        analysis = context["shared_context"].get(self.name, {})
        
        previous_speaker = analysis.get("speaker")
        next_speaker = analysis.get("underparticipating_students")

        # Validate correct use of student names (PRIORITY: This is critical)
        validation_error = self._validate_student_names(
            llm_response, previous_speaker, next_speaker
        )
        if validation_error:
            logging.warning(f"[Name Validation Failed] {validation_error}")
            return {
                "action": ValidationAction.REVISE,
                "feedback": validation_error,
            }

        return {"action": ValidationAction.PASS, "feedback": None}

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
        return context["llm_draft_response"]

    def _make_json_serializable(self, obj: Any) -> Any:
        """Recursively converts non-JSON-serializable objects to serializable forms.
        
        This handles:
        - ValidationAction enums -> their string values
        - Sets -> lists
        - Other nested structures recursively
        """
        if isinstance(obj, ValidationAction):
            return obj.value
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._make_json_serializable(item) for item in obj)
        else:
            return obj

    async def save_session(self, final_context: FrameContext) -> None:
        """Saves the final frame memory and log to a file."""
        # This is now an async method to allow for the summary generation call.
        # The engine will need to be updated to `await` this.
        frame_memory = final_context["frame_memory"]
        
        # Convert sets to lists for JSON serialization
        participation = frame_memory.get("participation", {})
        for student_data in participation.values():
            if isinstance(student_data.get("concepts_understood"), set):
                student_data["concepts_understood"] = list(student_data["concepts_understood"])
            if isinstance(student_data.get("concepts_confused"), set):
                student_data["concepts_confused"] = list(student_data["concepts_confused"])
        
        summary = await self._generate_session_summary(frame_memory)

        # Make validation results JSON-serializable by converting Enum to string
        validation_results = final_context.get("validation_results", {})
        serializable_validation_history = {}
        for frame_name, result in validation_results.items():
            # Copy the result so we don't mutate the original state
            serializable_result = result.copy()
            if "action" in serializable_result and isinstance(serializable_result["action"], ValidationAction):
                serializable_result["action"] = serializable_result["action"].value
            serializable_validation_history[frame_name] = serializable_result

        session_data = {
            "session_id": self.session_id,
            "final_frame_memory": frame_memory,
            "conversation_log": self.session_log,
            "conversation_history": final_context.get("conversation_history", []),
            "validation_history": serializable_validation_history,
            "summary": summary,
        }
        
        # Recursively make all data JSON-serializable
        session_data = self._make_json_serializable(session_data)
        
        # Separate file I/O from data formatting
        self._write_log_file(f"session_{self.session_id}.json", session_data)
        self._write_markdown_log_file(f"session_{self.session_id}.md", session_data)

    async def _generate_session_summary(self, frame_memory: Dict[str, Any]) -> Dict[str, str]:
        """Generates a summary of each student's participation and understanding."""
        participation_data = frame_memory.get("participation", {})
        if not participation_data:
            return {}

        summary_prompt = f"""
        You are an expert AI assistant tasked with summarizing a collaborative learning session.
        Based on the following participation data, generate a concise, one-paragraph summary for each student, highlighting their contribution count and the evolution of their understanding.

        **PARTICIPATION DATA:**
        {json.dumps(participation_data, indent=2)}

        **TASK:**
        Return a JSON object where the keys are the student names and the values are their individual summaries.

        **JSON OUTPUT EXAMPLE:**
        {{
            "StudentA": "Contributed 5 times, starting with some misconceptions but demonstrating intermediate understanding by the end of the session.",
            "StudentB": "Contributed 8 times, showing a strong grasp of the material from the beginning and helping to guide the mnemonic creation."
        }}
        """
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=summary_prompt)])
            summary_json = getattr(response, "content", "{}")
            summary_json = summary_json.strip().replace("```json", "").replace("```", "")
            return json.loads(summary_json)
        except (json.JSONDecodeError, Exception) as e:
            logging.error("Failed to generate session summary: %s", e)
            return {"error": "Failed to generate summary."}

    def _write_log_file(self, filename: str, data: Dict[str, Any]) -> None:
        """Handles the file system operations for saving the log."""
        _SESSION_LOG_DIR.mkdir(exist_ok=True)
        file_path = _SESSION_LOG_DIR / filename
        with file_path.open("w") as f:
            json.dump(data, f, indent=4)
        logging.info("[Marty] %s", _SESSION_LOG_SAVE_MSG.format(file_path))

    def _write_markdown_log_file(self, filename: str, session_data: Dict[str, Any]) -> None:
        """Handles the file system operations for saving the log in Markdown format."""
        _SESSION_LOG_DIR.mkdir(exist_ok=True)
        file_path = _SESSION_LOG_DIR / filename
        frame_memory = session_data.get("final_frame_memory", {})
        conversation_history = session_data.get("conversation_history", [])
        
        with file_path.open("w") as f:
            # Header
            f.write(f"# Session Report: {session_data.get('session_id', 'Unknown')}\n\n")
            
            # Summary section first
            summary = session_data.get("summary", {})
            if summary:
                f.write("## Session Summary\n\n")
                for student in self.students:
                    if student in summary:
                        f.write(f"**{student}:** {summary[student]}\n\n")
            
            # Time tracking per phase
            f.write("## Session Timeline\n\n")
            start_time = datetime.fromisoformat(frame_memory.get("start_time", datetime.now().isoformat()))
            f.write(f"**Session Start:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for phase_num in [1, 2, 3]:
                phase_key = f"phase_{phase_num}_start"
                if phase_key in frame_memory:
                    phase_time = datetime.fromisoformat(frame_memory[phase_key])
                    duration = (phase_time - start_time).total_seconds() / 60
                    f.write(f"**Phase {phase_num} Start:** {phase_time.strftime('%H:%M:%S')} (after {duration:.1f} minutes)\n\n")
            
            # Participation Summary (per student, at the top)
            f.write("## Participant Summary\n\n")
            participation = frame_memory.get("participation", {})
            for student, p_data in participation.items():
                f.write(f"### {student}\n")
                f.write(f"- **Total Contributions:** {p_data.get('contribution_count', 0)}\n")
                concepts_understood = p_data.get('concepts_understood', [])
                concepts_confused = p_data.get('concepts_confused', [])
                f.write(f"- **Concepts Understood:** {', '.join(concepts_understood) if concepts_understood else 'None yet'}\n")
                f.write(f"- **Concepts Confused:** {', '.join(concepts_confused) if concepts_confused else 'None'}\n")
                
                # Show understanding progression (first and last entries)
                understanding_history = p_data.get('understanding_history', [])
                if understanding_history:
                    first = understanding_history[0]
                    last = understanding_history[-1]
                    f.write(f"- **Understanding Progression:** Started at turn {first['turn']} ({first['level']}), ")
                    if len(understanding_history) > 1:
                        f.write(f"ended at turn {last['turn']} ({last['level']})\n")
                    else:
                        f.write("only one assessment\n")
                f.write("\n")
            
            # Turn-by-turn conversation log (chronological, like a chat)
            f.write("## Conversation Log (Turn-by-Turn)\n\n")
            
            # Build turn data from conversation log
            turn_data = {}
            for entry in session_data.get("conversation_log", []):
                event_data = entry.get("data", {})
                turn_num = event_data.get("turn_count")
                if turn_num:
                    if turn_num not in turn_data:
                        turn_data[turn_num] = {
                            "timestamp": entry["timestamp"],
                            "speaker": event_data.get("speaker"),
                            "message": event_data.get("message"),
                            "phase": event_data.get("session_phase"),
                            "concepts_understood": event_data.get("concepts_understood", []),
                            "concepts_confused": event_data.get("concepts_confused", []),
                            "concepts_for_mnemonic": event_data.get("concepts_mentioned_for_mnemonic", []),
                            "is_relevant": event_data.get("is_relevant", True),
                            "contribution_type": event_data.get("contribution_type", "N/A"),
                            "response": None
                        }
            
            # Match Marty's responses from conversation history
            # Conversation history alternates: [user, assistant, user, assistant, ...]
            # Turn 1: user message at index 0, assistant at index 1
            # Turn 2: user message at index 2, assistant at index 3
            for turn_num in sorted(turn_data.keys()):
                user_msg_idx = (turn_num - 1) * 2
                assistant_msg_idx = user_msg_idx + 1
                if assistant_msg_idx < len(conversation_history):
                    turn_data[turn_num]["response"] = conversation_history[assistant_msg_idx].get("content", "")
            
            # Write conversation in chronological order
            for turn_num in sorted(turn_data.keys()):
                turn = turn_data[turn_num]
                timestamp = datetime.fromisoformat(turn["timestamp"])
                
                f.write(f"### Turn {turn_num} (Phase {turn['phase']}) - {timestamp.strftime('%H:%M:%S')}\n\n")
                
                # Student message
                f.write(f"**{turn['speaker']}:** {turn['message']}\n\n")
                
                # Brief analysis (compact, key info only)
                if not turn['is_relevant']:
                    f.write("*[Off-topic]*\n\n")
                elif turn['concepts_confused']:
                    f.write(f"*Confused about: {', '.join(turn['concepts_confused'])}*\n\n")
                elif turn['concepts_understood']:
                    f.write(f"*Understood: {', '.join(turn['concepts_understood'])}*\n\n")
                
                # Marty's response
                if turn["response"]:
                    f.write(f"**Marty:** {turn['response']}\n\n")
                
                f.write("---\n\n")

            # Final Mnemonic Section
            final_mnemonic = frame_memory.get("current_mnemonic")
            if final_mnemonic:
                f.write("## Final Mnemonic\n\n")
                f.write(f"{final_mnemonic}\n\n")

        logging.info("[Marty] Session Markdown log saved to %s", file_path)

    def _log_event(self, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Adds a structured entry to the in-memory session log."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": message,
            "data": data or {},
        }
        self.session_log.append(log_entry)
        # Use debug level for verbose internal logging.
        logging.debug("Logged event: %s", message)
