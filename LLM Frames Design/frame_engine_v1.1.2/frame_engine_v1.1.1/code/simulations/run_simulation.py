"""
Automated Multi-Turn Simulation for Marty Frame Engine v1.1.1
Using Azure OpenAI (SBS Marty deployment)

This script adapts the original azure_simulation.py to work with the
FrameEngineV1 architecture. It is designed to be located in the
`frame_engine_v1.1.1/simulations` directory.

Usage:
    # From the `frame_engine_v1.1.1` directory:
    # python simulations/run_simulation.py --scenario balanced_session --turns 25
"""
import argparse
import asyncio
import os
import random
import sys
from datetime import datetime
from typing import Dict
from pathlib import Path

# --- Path Setup ---
# This is the key to solving the import errors. We need to explicitly add
# the 'src' directory to the Python path so that when this script is run,
# Python knows where to find the 'backend' package.

# Get the directory of the current script (simulations/)
script_dir = Path(__file__).parent.resolve()
# Get the parent directory (code/)
code_dir = script_dir.parent
# Get the path to the 'src' directory
src_path = code_dir / 'src'

# Add 'src' to the Python path
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


import google.generativeai as genai
from dotenv import load_dotenv
import yaml


from backend.frame_engine.engine import FrameEngine
from backend.frames.language_checker import LanguageCheckerFrame
from backend.frames.phases_checker import PhasesCheckerFrame, PHASE_GOALS
from backend.frames.comprehension_tracker import ComprehensionTrackerFrame
from backend.frames.marty import MnemonicCoCreatorFrame
from backend.frames.balanced_turns import BalancedTurnsFrame
from backend.frame_engine.core import SessionLogger, SessionVerbosity
from backend.frame_engine.llm import get_llm_client


def get_next_simulation_number(sessions_dir: Path) -> int:
    """Gets the next simulation number based on existing session files."""
    if not sessions_dir.exists():
        return 1
    
    # Count existing .yaml files (each session creates a .yaml and .md)
    existing_sessions = list(sessions_dir.glob("session_*.yaml"))
    return len(existing_sessions) + 1


# --- Load Environment Variables ---
# Load the .env file from the specified path
# Since this script is in `code/simulations`, the .env is in `../scripts/.env`
dotenv_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'scripts', '.env'
))
if not load_dotenv(dotenv_path):
    print(f"Warning: Could not find the .env file at {dotenv_path}")
    print("Please ensure the .env file with API keys is in the correct location.")

# Google API Configuration (loaded from environment variables)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("Error: GOOGLE_API_KEY must be set in the .env file.")
    sys.exit(1)


# --- Robust Path Definitions ---
# Get the absolute path to the directory where this script is located
SIMULATIONS_DIR = os.path.abspath(os.path.dirname(__file__))
# The `code` directory is the parent of the `simulations` directory
CODE_DIR = os.path.abspath(os.path.join(SIMULATIONS_DIR, '..'))
# Get the root of the frame_engine_v1.1.1 directory
FRAME_ENGINE_ROOT = os.path.abspath(os.path.join(CODE_DIR, '..'))

def read_file_from_path(file_path: str) -> str:
    """Reads a file from a given absolute path."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Asset file not found at '{file_path}'")
        sys.exit(1)

# Load learning material from the frame engine root
LEARNING_MATERIAL = read_file_from_path(os.path.join(FRAME_ENGINE_ROOT, "microcontrollers.md"))

# Load persona templates from the local personas directory
RED_PERSONA_TEMPLATE = read_file_from_path(os.path.join(SIMULATIONS_DIR, "personas/STUDENT_RED_PERSONA.md"))
BLUE_PERSONA_TEMPLATE = read_file_from_path(os.path.join(SIMULATIONS_DIR, "personas/STUDENT_BLUE_PERSONA.md"))
GREEN_PERSONA_TEMPLATE = read_file_from_path(os.path.join(SIMULATIONS_DIR, "personas/STUDENT_GREEN_PERSONA.md"))


class SimulationOrchestrator:
    """Orchestrates automated multi-turn conversations using the FrameEngine."""

    def __init__(
        self,
        scenario_name: str,
        max_turns: int = 25,
        target_age: int = 14,
        student_model_name: str = "gemini-1.5-flash-latest",
        mnemonic_type: str = "Story",
    ):
        self.scenario_name = scenario_name
        self.max_turns = max_turns
        self.target_age = target_age
        self.student_model_name = student_model_name
        self.mnemonic_type = mnemonic_type
        self.conversation_history = []
        # REMOVED: self.turn_count = 0. The frame is the source of truth.
        self.frame_memory = {}
        self.students = ["Red", "Blue", "Green"]
        self.last_marty_response = ""  # Track Marty's last response
        self.phase_transitions = []  # Track phase transitions: [(phase, turn, elapsed_time)]
        self.current_phase = 1  # Track current phase for transition detection
        
        # Customize personas with mnemonic type
        self.personas = self._load_personas_with_mnemonic_type()

        # --- Student Model Setup ---
        # Configure the Google AI client here for better encapsulation
        genai.configure(api_key=GOOGLE_API_KEY)
        self.student_model = genai.GenerativeModel(self.student_model_name)
        print(f"✅ Student simulation using Google AI model: {self.student_model_name}")

        # --- Frame Engine Setup ---
        # Load the main config (SAME as frontend) to get the LLM provider and model
        config_path = Path(CODE_DIR) / 'scripts' / 'config.yaml'
        with config_path.open('r') as f:
            self.app_config = yaml.safe_load(f)

        llm_config = self.app_config.get('llm', {})
        engine_provider = llm_config.get('provider', 'google')
        engine_model = llm_config.get('model_name', 'gemini-2.5-flash-lite')


        # Initialize the LLM client for the Frame Engine (same logic as frontend)
        self.llm_client = get_llm_client(
            provider=engine_provider,
            model_name=engine_model,
            temperature=llm_config.get('temperature', 0.7),
        )
        print(f"✅ Frame Engine using {engine_provider}: {engine_model}")

        # Sessions will be saved inside the `simulations` folder
        sessions_dir = Path(os.path.join(os.path.dirname(__file__), "sessions"))
        sim_number = get_next_simulation_number(sessions_dir)
        self.session_logger = SessionLogger(
            session_id=f"sim{sim_number:03d}_{self.scenario_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            verbosity=SessionVerbosity.VERBOSE,
            output_dir=sessions_dir
        )
        
        # Set session metadata (same as frontend lines 122-126)
        self.session_logger.set_metadata('topic', 'Microcontrollers')
        self.session_logger.set_metadata('mnemonic_type', self.mnemonic_type)
        self.session_logger.set_metadata('students', self.students)
        self.session_logger.set_metadata('target_age', self.target_age)
        self.session_logger.set_metadata('scenario', self.scenario_name)
        self.session_logger.log('Simulation initialized')
        # The following lines were removed as per the edit hint:
        # self.llm_client = AzureChatOpenAI(
        #     azure_deployment=AZURE_DEPLOYMENT,
        #     api_version=API_VERSION,
        #     azure_endpoint=AZURE_ENDPOINT,
        #     api_key=AZURE_API_KEY,
        # )
        self.frame_engine = self._initialize_frame_engine()

    def _load_personas_with_mnemonic_type(self) -> dict[str, str]:
        """Load and customize personas with the selected mnemonic type."""
        personas = {
            "Red": RED_PERSONA_TEMPLATE,
            "Blue": BLUE_PERSONA_TEMPLATE,
            "Green": GREEN_PERSONA_TEMPLATE,
        }
        
        # Simply replace template variables with actual mnemonic type
        customized_personas = {}
        for name, template in personas.items():
            customized = template.replace("{MNEMONIC_TYPE}", self.mnemonic_type.upper())
            customized = customized.replace("{MNEMONIC_TYPE_LOWER}", self.mnemonic_type.lower())
            customized_personas[name] = customized
        
        return customized_personas

    def _initialize_frame_engine(self) -> FrameEngine:
        """Initializes the FrameEngine with required frames.
        
        Uses the SAME frame configuration as the frontend to ensure consistency.
        """
        # Get phase config from app config (same as frontend)
        phase_config = self.app_config.get('phases', {'phase_1_end': 5, 'phase_2_end': 20})

        # Initialize frames in the SAME ORDER as frontend.py (lines 129-150)
        marty_frame = MnemonicCoCreatorFrame(
            topic="Microcontrollers",
            learning_material=LEARNING_MATERIAL,
            students=self.students,
            mnemonic_type=self.mnemonic_type,
            phase_config=phase_config,
            llm_client=self.llm_client,
            target_age=self.target_age,
        )
        
        comprehension_frame = ComprehensionTrackerFrame(
            learning_material=LEARNING_MATERIAL,
            students=self.students,
            llm_client=self.llm_client,
        )
        
        balanced_turns_frame = BalancedTurnsFrame(
            students=self.students
        )
        
        language_checker_frame = LanguageCheckerFrame(
            target_age=self.target_age,
            llm_client=self.llm_client
        )
        
        phases_checker_frame = PhasesCheckerFrame(
            llm_client=self.llm_client
        )

        # Create engine with SAME frame order as frontend
        engine = FrameEngine(
            frames=[
                marty_frame,
                comprehension_frame,
                balanced_turns_frame,  # Validates turn-taking after Marty's analysis
                language_checker_frame,
                phases_checker_frame,
            ],
            llm_client=self.llm_client,
            session_logger=self.session_logger
        )
        print("✅ FrameEngine V1.1.1 Initialized with 5 frames (same config as frontend)")
        return engine

    def _initialize_memory(self) -> Dict:
        """DEPRECATED: This is no longer needed as frames initialize their own memory."""
        return {}

    def _estimate_elapsed_time(self, user_input: str) -> float:
        """Estimates realistic elapsed time for the simulation.
        
        Real sessions take ~10 minutes total:
        - Phase 1 (concept selection): 0-3 minutes
        - Phase 2 (mnemonic creation): 3-9 minutes  
        - Phase 3 (practice/recall): 9+ minutes
        
        We estimate time based on turn count and message length to simulate realistic pacing.
        """
        turn_count = self.frame_memory.get('turn_count', 0) + 1  # Next turn
        
        # Base time: ~0.5 minutes per turn (students think, type, Marty responds)
        base_time_per_turn = 0.5
        
        # Adjust for message length (longer messages = more time)
        # Average message is ~50 chars, so scale accordingly
        char_count = len(user_input)
        length_factor = max(0.7, min(1.3, char_count / 50))  # 0.7x to 1.3x
        
        # Calculate estimated elapsed time
        estimated_time = turn_count * base_time_per_turn * length_factor
        
        return round(estimated_time, 1)

    async def call_marty_engine(self, user_input: str) -> Dict:
        """Calls the FrameEngine to get Marty's response."""
        print(f"\n[🤖 MARTY ENGINE]")
        
        # Inject realistic elapsed time into frame_memory for simulation
        estimated_time = self._estimate_elapsed_time(user_input)
        self.frame_memory['elapsed_time_minutes'] = estimated_time

        result = await self.frame_engine.ainvoke(
            user_input=user_input,
            conversation_history=self.conversation_history,
            frame_memory=self.frame_memory
        )
        return result

    def call_student(self, student_color: str) -> str:
        """Call the Google AI model with the student persona."""
        print(f"[👤 {student_color.upper()}]")

        persona = self.personas[student_color]
        
        # Get Marty's last message to respond to.
        last_marty_message = "No message yet."
        if self.conversation_history and self.conversation_history[-1]['role'] == 'assistant':
            last_marty_message = self.conversation_history[-1]['content']

        # Create a single, comprehensive prompt that is less likely to confuse the LLM
        full_prompt = f"""You are roleplaying as a 14-year-old student named {student_color}.
Your persona and current knowledge are described below.

---
PERSONA AND KNOWLEDGE:
{persona}
---

Marty just said: "{last_marty_message}"

It is now your turn to speak.
Based on your persona and what Marty just said, provide a short, casual, 1-2 sentence response.
Your response MUST start with "{student_color}: ".
"""
        try:
            response = self.student_model.generate_content(full_prompt)
            message = response.text.strip()

            if not message:
                return f"{student_color}: [Empty response]"

            # Ensure the response starts correctly
            if not message.startswith(f"{student_color}:"):
                message = f"{student_color}: {message}"
            return message

        except Exception as e:
            print(f"Error calling {student_color} (Google AI): {e}")
            return f"{student_color}: [Error generating response]"

    def add_message_to_history(self, role: str, content: str, role_name: str):
        """Adds a message to the conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "role_name": role_name
        })

    def get_next_student(self) -> str:
        """Determine the next speaker, prioritizing students asked a question."""
        # 1. Check if a student name appears at the start (direct address)
        # e.g., "Blue, what do you think?" or "Red, can you help?"
        for name in self.students:
            # Look for pattern: name at start, possibly followed by comma or question
            if self.last_marty_response.startswith(name):
                print(f"✅ Marty directly addressed {name}, giving them the turn.")
                return name
        
        # 2. If question exists, find the CLOSEST student name BEFORE the question mark
        # This handles: "What do you think, Blue?"
        if '?' in self.last_marty_response:
            question_part = self.last_marty_response.rsplit('?', 1)[0]
            last_mention_pos = -1
            next_speaker = None
            for name in self.students:
                pos = question_part.rfind(name)
                if pos > last_mention_pos:
                    last_mention_pos = pos
                    next_speaker = name
            
            if next_speaker:
                print(f"✅ Marty asked a question to {next_speaker}, giving them the turn.")
                return next_speaker

        # 3. Fallback to any mention if no question is detected.
        for student_name in self.students:
            if student_name in self.last_marty_response:
                print(f"✅ Marty mentioned {student_name}, giving them the turn.")
                return student_name

        # 3. If no one was called out, fall back to the balanced strategy.
        participation = self.frame_memory.get("participation", {})

        # The authoritative turn_count is in the frame's memory
        current_turn = self.frame_memory.get('turn_count', 0)

        if not participation:
            # If participation data isn't initialized yet, just cycle through students.
            # This is a fallback for the very first student turn.
            return self.students[current_turn % len(self.students)]

        counts = {
            s: p_data.get("contribution_count", 0)
            for s, p_data in participation.items()
        }
        return min(counts, key=counts.get)
    
    def _track_phase_transition(self, turn: int):
        """Track when phases transition for the markdown report."""
        phase = self.frame_memory.get("session_phase", 1)
        elapsed_time = self.frame_memory.get("elapsed_time_minutes", 0)
        
        # Detect phase transition
        if phase != self.current_phase:
            self.phase_transitions.append({
                'phase': phase,
                'turn': turn,
                'elapsed_time': elapsed_time
            })
            self.current_phase = phase
            print(f"🔄 PHASE TRANSITION: Entered Phase {phase} at Turn {turn} ({elapsed_time:.1f} min)")
    
    def _print_phase_tracker(self, turn: int):
        """Print the current phase, goal, and progress - READ ONLY from frame."""
        # Frame memory is flat, not nested under frame names
        phase = self.frame_memory.get("session_phase", 1)
        elapsed_time = self.frame_memory.get("elapsed_time_minutes", 0)
        turn_count = self.frame_memory.get("turn_count", turn)
        
        # Get goal from PHASE_GOALS constant (shared with PhasesCheckerFrame)
        goal = PHASE_GOALS.get(phase, "Unknown phase")
        
        print(f"\n📊 PHASE TRACKER (Turn {turn})")
        print(f"├─ Current Phase: {phase}/3")
        print(f"├─ Goal: {goal}")
        print(f"├─ Turn Count: {turn_count}")
        print(f"└─ Elapsed Time: {elapsed_time:.1f} min\n")

    async def run_simulation(self):
        """Run the complete simulation with proper Student→Marty alternation."""
        print(f"\n{'='*70}")
        print(f"AUTOMATED SIMULATION: {self.scenario_name}")
        print(f"Max Turns: {self.max_turns}")
        print(f"Student Model: {self.student_model_name}")
        print(f"{'='*70}\n")

        # --- Turn 1: Manual Start ---
        current_turn = 1
        # Randomize the starting student for fair testing
        initial_student = random.choice(self.students)
        other_students = [s for s in self.students if s != initial_student]
        
        # Format mnemonic type correctly (Jokes = no article, Story/Poem = with article)
        mnemonic_phrase = f"create {self.mnemonic_type.lower()}" if self.mnemonic_type.lower() == "jokes" else f"create a {self.mnemonic_type.lower()}"
        
        initial_message = f"{initial_student}: Hey Marty! I'm {initial_student} and I'm working with {other_students[0]} and {other_students[1]} on microcontrollers and we need to {mnemonic_phrase}."

        print(f"[👤 {initial_student.upper()} - Turn {current_turn}]")
        print(f"✓ {initial_message}")

        # Marty's first response
        engine_result = await self.call_marty_engine(initial_message)
        self.last_marty_response = engine_result['response']
        self.frame_memory = engine_result['final_state']['frame_memory']
        self.conversation_history = engine_result['final_state']['conversation_history']

        print(f"[🤖 MARTY - Turn {current_turn}]")
        print(f"✓ Marty: {self.last_marty_response[:100]}...")
        
        # Track phase transition
        self._track_phase_transition(current_turn)
        
        # Show phase tracker
        self._print_phase_tracker(current_turn)

        # --- Subsequent Turns Loop ---
        # Each iteration: Student speaks → Marty responds
        while current_turn < self.max_turns:
            current_turn += 1

            # 1. Student's Turn
            student = self.get_next_student()
            student_message = self.call_student(student)
            
            print(f"\n[👤 {student.upper()} - Turn {current_turn}]")
            print(f"✓ {student_message}")

            # 2. Marty's Turn - Respond to this student
            engine_result = await self.call_marty_engine(student_message)
            self.last_marty_response = engine_result['response']
            self.frame_memory = engine_result['final_state']['frame_memory']
            self.conversation_history = engine_result['final_state']['conversation_history']

            print(f"[🤖 MARTY - Turn {current_turn}]")
            print(f"✓ Marty: {self.last_marty_response[:100]}...")
            
            # Track phase transition
            self._track_phase_transition(current_turn)
            
            # Show phase tracker
            self._print_phase_tracker(current_turn)

            # 3. Check for Completion
            phase = self.frame_memory.get("session_phase", 1)
            elapsed_time = self.frame_memory.get("elapsed_time_minutes", 0)
            
            # Allow Phase 3 to run for at least 2-3 turns for recall practice
            if phase == 3 and elapsed_time >= 10:
                print(f"\n{'='*70}")
                print("✓ SESSION COMPLETE - Phase 3 recall practice complete")
                print(f"{'='*70}")
                break

        await self.frame_engine.end_session(engine_result['final_state'])
        
        # Add participation summary to the MD file
        self._add_participation_summary(engine_result['final_state'])
    
    def _add_participation_summary(self, final_state: dict):
        """Add participation summary and mnemonic state to the markdown report."""
        from pathlib import Path
        
        session_id = self.session_logger.session_id
        output_dir = Path(self.session_logger.output_dir)
        md_file_path = output_dir / f'session_{session_id}.md'
        
        # Read the existing MD file
        if not md_file_path.exists():
            return
        
        with md_file_path.open('r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract data from frame_memory
        frame_memory = final_state.get('frame_memory', {})
        participation = frame_memory.get('participation')
        mnemonic_state = frame_memory.get('mnemonic_state', {})
        
        # Build the mnemonic type section
        type_descriptions = {
            "Story": "A narrative that weaves concepts together",
            "Poem": "Rhyming lines that capture key concepts",
            "Jokes": "Humorous setups and punchlines about concepts",
        }
        type_desc = type_descriptions.get(self.mnemonic_type, "A creative mnemonic device")
        mnemonic_type_section = "## 🎨 Mnemonic Type\n\n"
        mnemonic_type_section += f"**{self.mnemonic_type}** - {type_desc}\n\n"
        
        # Build the phase transitions section
        phase_transitions_section = ""
        if self.phase_transitions:
            phase_transitions_section = "## ⏱️ Phase Transitions\n\n"
            phase_transitions_section += "| Phase | Turn | Elapsed Time |\n"
            phase_transitions_section += "|-------|------|-------------|\n"
            for transition in self.phase_transitions:
                phase = transition['phase']
                turn = transition['turn']
                elapsed = transition['elapsed_time']
                phase_name = f"Phase {phase}"
                if phase == 1:
                    phase_name += " (Knowledge Building)"
                elif phase == 2:
                    phase_name += " (Mnemonic Creation)"
                elif phase == 3:
                    phase_name += " (Recall Practice)"
                phase_transitions_section += f"| {phase_name} | Turn {turn} | {elapsed:.1f} min |\n"
            phase_transitions_section += "\n"
        
        # Build the participation table
        participation_section = ""
        if participation:
            participation_section = "## 📊 Participation Summary\n\n"
            participation_section += "| Student | Contributions | Speaking Time |\n"
            participation_section += "|---------|---------------|---------------|\n"
            for student, p_data in sorted(participation.items()):
                count = p_data.get('contribution_count', 0)
                time = p_data.get('total_speaking_time_seconds', 0)
                participation_section += f"| **{student}** | {count} | {time:.1f}s |\n"
            participation_section += "\n"
        
        # Build the comprehension tracker section
        comprehension_sections = ""
        comprehension_tracker = frame_memory.get('comprehension_tracker', {})
        by_student = comprehension_tracker.get('by_student', {})
        
        if by_student:
            comprehension_sections = "## 🧠 Comprehension Summary\n\n"
            for student_name in sorted(by_student.keys()):
                student_concepts = by_student[student_name]
                understood = []
                confused = []
                
                for concept, data in student_concepts.items():
                    level = data.get('level', 'not_seen')
                    if level == 'understood':
                        understood.append(concept)
                    elif level == 'confused':
                        confused.append(concept)
                
                if understood or confused:
                    comprehension_sections += f"### {student_name}\n\n"
                    if understood:
                        comprehension_sections += f"**✅ Understood:** {', '.join(understood)}\n\n"
                    if confused:
                        comprehension_sections += f"**❓ Confused:** {', '.join(confused)}\n\n"
        
        # Build the mnemonic state sections
        mnemonic_sections = ""
        
        # Selected concepts section
        selected_concepts = mnemonic_state.get('selected_concepts', [])
        concepts_finalized = mnemonic_state.get('concepts_finalized', False)
        if selected_concepts:
            mnemonic_sections += "## 🎯 Selected Concepts\n\n"
            mnemonic_sections += f"**Status:** {'✅ Finalized' if concepts_finalized else '⏳ In Progress'}\n\n"
            for i, concept in enumerate(selected_concepts, 1):
                mnemonic_sections += f"{i}. {concept}\n"
            mnemonic_sections += "\n"
        else:
            mnemonic_sections += "## 🎯 Selected Concepts\n\n"
            mnemonic_sections += "**Status:** ❌ No concepts selected\n\n"
        
        # Mnemonic created section
        mnemonic_text = mnemonic_state.get('mnemonic_text', '')
        mnemonic_created = mnemonic_state.get('mnemonic_created', False)
        if mnemonic_text and mnemonic_created:
            mnemonic_sections += "## 📖 Created Mnemonic\n\n"
            mnemonic_sections += f"**Status:** ✅ Complete\n\n"
            mnemonic_sections += f"{mnemonic_text}\n\n"
        else:
            mnemonic_sections += "## 📖 Created Mnemonic\n\n"
            mnemonic_sections += "**Status:** ❌ No mnemonic created\n\n"
        
        # Insert sections after "**Saved at:**" line
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            new_lines.append(line)
            if line.startswith('**Saved at:**'):
                new_lines.append('')
                # Add mnemonic type
                new_lines.extend(mnemonic_type_section.split('\n'))
                # Add phase transitions
                if phase_transitions_section:
                    new_lines.extend(phase_transitions_section.split('\n'))
                # Add participation summary
                if participation_section:
                    new_lines.extend(participation_section.split('\n'))
                # Add comprehension summary
                if comprehension_sections:
                    new_lines.extend(comprehension_sections.split('\n'))
                # Add mnemonic state sections
                new_lines.extend(mnemonic_sections.split('\n'))
        
        # Write back
        with md_file_path.open('w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run automated Marty simulation with FrameEngineV1")
    parser.add_argument("--scenario", type=str, default="auto_test", help="Scenario name")
    parser.add_argument("--turns", type=int, default=25, help="Maximum turns")
    parser.add_argument("--age", type=int, default=14, help="Target age for the session")
    parser.add_argument(
        "--mnemonic_type",
        type=str,
        default="Story",
        choices=["Story", "Poem", "Jokes"],
        help="Type of mnemonic to create (Story, Poem, or Jokes)",
    )
    parser.add_argument(
        "--student_model",
        type=str,
        default="gemini-2.5-flash-lite",  # Use the same flash model as the app
        help="Google AI model to use for student simulation",
    )

    args = parser.parse_args()

    orchestrator = SimulationOrchestrator(
        scenario_name=args.scenario,
        max_turns=args.turns,
        target_age=args.age,
        student_model_name=args.student_model,
        mnemonic_type=args.mnemonic_type,
    )

    await orchestrator.run_simulation()


if __name__ == "__main__":
    print("="*70)
    print("MARTY FRAME ENGINE V1.1.1 - AUTOMATED SIMULATION")
    print("="*70)
    
    if len(sys.argv) > 1:
        asyncio.run(main())
    else:
        print("\nRunning demo simulation (15 turns, age 14)...\n")
        orchestrator = SimulationOrchestrator(
            scenario_name="demo",
            max_turns=15,
            target_age=14,
            student_model_name="gemini-2.5-flash-lite", # Use the same flash model as the app
        )
        asyncio.run(orchestrator.run_simulation())
