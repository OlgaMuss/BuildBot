"""A frame that facilitates a collaborative mnemonic creation session."""
import json
import logging
import re
from datetime import datetime
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
- Conversation History:
{history}

**STUDENT MESSAGE:**
"{speaker}: {message}"

**ANALYSIS TASK:**
Analyze the student's message and provide the following in a JSON object:
1.  `contribution_type`: Classify the message. Choose one: "mnemonic_suggestion", "knowledge_statement", "question", "builds_on_idea", "off_topic".
2.  `understanding_level`: Assess the student's grasp of the topic based on this message. Choose one: "beginner", "intermediate", "advanced", "misconception".
3.  `is_relevant`: A boolean (`true` or `false`) indicating if the message is relevant to the topic or task.
4.  `mnemonic_progress`: A brief, one-sentence summary of the current state of the co-created mnemonic.
5.  `summary`: A one-sentence summary of the student's message.

**JSON OUTPUT EXAMPLE:**
{{
  "contribution_type": "mnemonic_suggestion",
  "understanding_level": "intermediate",
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
        self.session_log: list[dict] = []

    @property
    def name(self) -> str:
        """Returns the unique name of the frame."""
        return "mnemonic_co_creator_marty"

    # --- Helper Methods for Analyze Input (Single Responsibility) ---

    def _initialize_memory(self, frame_memory: Dict[str, Any]) -> None:
        """Sets up the initial state in `frame_memory` for a new session."""
        frame_memory["turn_count"] = 0
        frame_memory["session_phase"] = 1
        frame_memory["consecutive_off_topic_turns"] = 0
        frame_memory["participation"] = {
            student: {"contribution_count": 0} for student in self.students
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

    def _update_participation(
        self, frame_memory: Dict[str, Any], speaker: str
    ) -> List[str]:
        """Tracks student contributions and identifies who has not yet spoken."""
        if speaker in frame_memory["participation"]:
            frame_memory["participation"][speaker]["contribution_count"] += 1

        # Identify students who have contributed significantly less than others.
        counts = [
            data["contribution_count"]
            for data in frame_memory["participation"].values()
        ]
        if not counts or max(counts) < 2:
            return []
        
        min_contributions = min(counts)
        if (max(counts) - min_contributions) < 2:
            return []

        underparticipating = [
            name
            for name, data in frame_memory["participation"].items()
            if data["contribution_count"] == min_contributions
        ]
        return underparticipating

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
        phase = self._get_current_phase(turn)
        frame_memory["session_phase"] = phase

        speaker, message = self._parse_user_input(user_input)
        underparticipating = self._update_participation(frame_memory, speaker)

        # Perform the deep analysis using an LLM call.
        llm_analysis = await self._run_llm_analysis(
            context, speaker, message, turn, phase
        )

        # Track off-topic duration
        if llm_analysis.get("is_relevant") is False:
            frame_memory["consecutive_off_topic_turns"] += 1
        else:
            frame_memory["consecutive_off_topic_turns"] = 0

        # Consolidate all findings for shared_context.
        analysis_output = {
            "turn_count": turn,
            "speaker": speaker,
            "message": message,
            "participation": frame_memory["participation"],
            "session_phase": phase,
            "underparticipating_students": underparticipating,
            "off_topic_duration": frame_memory["consecutive_off_topic_turns"],
            **llm_analysis,  # Add the rich analysis from the LLM
        }

        self._log_event("Analysis complete.", analysis_output)
        return analysis_output

    def _get_current_phase(self, turn_count: int) -> int:
        """Determines the current session phase based on the turn count."""
        if turn_count <= self.phases.get("phase_1_end", 5):
            return 1
        elif turn_count <= self.phases.get("phase_2_end", 20):
            return 2
        return 3

    async def _run_llm_analysis(
        self, context: FrameContext, speaker: str, message: str, turn: int, phase: int
    ) -> Dict[str, Any]:
        """Uses an LLM to perform a deep analysis of the user's input.

        This internal method is the core of the frame's intelligence. It
        constructs a specialized prompt to ask an LLM to classify the user's
        contribution, assess their understanding, and check for relevance.
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
                "understanding_level": "unknown",
                "is_relevant": True,
                "summary": "Analysis failed.",
            }

    async def shape_prompt(self, context: FrameContext) -> str:
        """Constructs the system prompt based on the current session phase."""
        analysis = context["shared_context"][self.name]
        phase = analysis.get("session_phase", 1)
        underparticipating_students = analysis.get("underparticipating_students")
        understanding = analysis.get("understanding_level", "intermediate")
        off_topic_duration = analysis.get("off_topic_duration", 0)

        base_prompt = self._get_base_prompt()
        phase_instructions = self._get_phase_instructions(phase, understanding)
        participation_instructions = self._get_participation_instructions(
            underparticipating_students
        )
        relevance_instructions = self._get_relevance_instructions(off_topic_duration)

        return (
            base_prompt
            + phase_instructions
            + participation_instructions
            + relevance_instructions
        )

    def _get_base_prompt(self) -> str:
        """Returns the static, core part of the system prompt."""
        return f"""You are 'Marty,' a friendly and encouraging buddy robot facilitating a session for students to create a mnemonic about '{self.topic}'.
Your response must be concise (1-3 sentences) and focus on only 1-2 concepts per turn.
Base all your factual knowledge *exclusively* on the following material:
--- LEARNING MATERIAL ---
{self.learning_material.strip()}
-------------------------
"""

    def _get_phase_instructions(self, phase: int, understanding: str) -> str:
        """Returns the instructional part of the prompt for the current phase."""
        
        # Add specific structural guidance based on the chosen mnemonic type.
        type_guidance = ""
        if self.mnemonic_type == "Story":
            type_guidance = "Help the students create a coherent narrative that weaves all key concepts together."
        elif self.mnemonic_type == "Acronym":
            type_guidance = "Help the students build an acronym where each letter stands for a key concept."
        elif self.mnemonic_type == "Song":
            type_guidance = "Help the students write rhyming lines for a song that each capture a key concept."
        
        understanding_guidance = f"The student's current understanding seems to be at an '{understanding}' level. Adapt your language and the complexity of your questions accordingly."

        if phase == 1:
            return f"""
Current Goal: Collective Hook & Knowledge Building.
Your task is to facilitate a whole-group discussion. Ask open questions that help students identify what they know about the topic and what's unclear.
{understanding_guidance}
"""
        elif phase == 2:
            return f"""
Current Goal: Brainstorm Core Concepts.
Your task is to guide the students to select the 3-5 most critical concepts for their '{self.mnemonic_type}' mnemonic.
{type_guidance}
{understanding_guidance}
"""
        return f"""
Current Goal: Memorization & Practice.
Your task is to test the students' recall of the mnemonic. Ask them to recite parts or fill in the blanks. Encourage them to help each other remember. Reinforce the connection between the mnemonic and the actual concepts.
{type_guidance}
{understanding_guidance}
"""
    
    def _get_participation_instructions(self, students: Optional[List[str]]) -> str:
        """Generates an instruction to invite underparticipating students."""
        if not students:
            return ""
        
        student_list = " and ".join(students)
        invitation = f"Gently invite {student_list} to share their thoughts, for example: 'What do you think about this, {students[0]}?'"
        return f"\n{invitation}\n"

    def _get_relevance_instructions(self, off_topic_duration: int) -> str:
        """Generates an instruction to redirect if the conversation is off-topic."""
        if off_topic_duration < 2:
            return ""
        return "\nThe conversation has been off-topic for a couple of turns. Gently redirect the conversation back to the task of creating the mnemonic."

    async def validate_output(self, context: FrameContext) -> ValidationResult:
        """Validates the LLM's response for conciseness."""
        llm_response = context["llm_draft_response"]

        # This frame is now only responsible for checking the length of the
        # response. The check for direct answers has been moved to the
        # specialized AnswerCheckerFrame.
        if len(llm_response.split()) > 50:
            return {
                "action": ValidationAction.REVISE,
                "feedback": "Your response is too long. Keep it to 1-3 sentences.",
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

    def save_session(self, final_context: FrameContext) -> None:
        """Saves the final frame memory and log to a file."""
        session_data = {
            "session_id": self.session_id,
            "final_frame_memory": final_context["frame_memory"],
            "conversation_log": self.session_log,
        }
        
        # Separate file I/O from data formatting
        self._write_log_file(f"session_{self.session_id}.json", session_data)

    def _write_log_file(self, filename: str, data: Dict[str, Any]) -> None:
        """Handles the file system operations for saving the log."""
        _SESSION_LOG_DIR.mkdir(exist_ok=True)
        file_path = _SESSION_LOG_DIR / filename
        with file_path.open("w") as f:
            json.dump(data, f, indent=4)
        logging.info("[Marty] %s", _SESSION_LOG_SAVE_MSG.format(file_path))

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
