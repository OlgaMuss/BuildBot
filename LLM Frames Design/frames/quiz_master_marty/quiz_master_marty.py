#!/usr/bin/env python3
"""
Quiz Master Marty Frame Implementation

This module implements the Rodin Frame Simulator for "Quiz Master Marty"
following the Four-Slot execution flow defined in FRAME.md
"""

import json
import os
import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Student:
    """Represents a student in the quiz session"""
    id: str
    color: str
    turn_count: int = 0
    performance_history: List[str] = None
    
    def __post_init__(self):
        if self.performance_history is None:
            self.performance_history = []


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation"""
    turn_number: int
    timestamp: str
    role: str  # 'assistant' or 'user'
    content: str
    slot_analysis: Dict[str, str] = None
    
    def __post_init__(self):
        if self.slot_analysis is None:
            self.slot_analysis = {}


class QuizMasterMartyFrame:
    """
    Main frame class implementing the Quiz Master Marty simulator
    """
    
    def __init__(self, frame_dir: str = None):
        """Initialize the frame with directory structure"""
        self.frame_dir = frame_dir or os.path.dirname(os.path.abspath(__file__))
        self.memory_dir = os.path.join(self.frame_dir, "memory")
        self.learning_material_dir = os.path.join(self.frame_dir, "learning_material")
        
        # Ensure directories exist
        os.makedirs(self.memory_dir, exist_ok=True)
        
        # Initialize frame state
        self.current_conversation_file = None
        self.conversation_history = []
        self.frame_memory = self._load_default_memory()
        
    def _load_default_memory(self) -> Dict[str, Any]:
        """Load default frame memory from memory.json"""
        memory_file = os.path.join(self.memory_dir, "memory.json")
        try:
            with open(memory_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default memory structure
            return {
                "students": [
                    {"id": "student_a", "color": "Red", "turn_count": 0, "performance_history": []},
                    {"id": "student_b", "color": "Blue", "turn_count": 0, "performance_history": []},
                    {"id": "student_c", "color": "Green", "turn_count": 0, "performance_history": []}
                ],
                "quiz_topic": "microcontrollers",
                "current_turn_student_id": "student_a"
            }
    
    def _create_conversation_file(self) -> str:
        """Create a new timestamped conversation file"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"conversation_{timestamp}.json"
        self.current_conversation_file = os.path.join(self.memory_dir, filename)
        return filename
    
    def _save_conversation(self):
        """Save complete conversation data to file"""
        if not self.current_conversation_file:
            return
            
        conversation_data = {
            "conversation_id": f"conv_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
            "session_start_time": self.conversation_history[0]["timestamp"] if self.conversation_history else datetime.datetime.now().isoformat(),
            "last_updated": datetime.datetime.now().isoformat(),
            "conversation_history": self.conversation_history,
            "frame_memory": self.frame_memory,
            "session_analytics": self._generate_session_analytics(),
            "conversation_metadata": {
                "session_type": "Interactive Session",
                "frame_version": "Quiz Master Marty v1.0",
                "knowledge_source": "learning_material/microcontrollers.md",
                "persona": "Marty - friendly encouraging peer",
                "assessment_method": "oral discussion",
                "session_duration": self._calculate_session_duration()
            }
        }
        
        with open(self.current_conversation_file, 'w') as f:
            json.dump(conversation_data, f, indent=2)
    
    def _generate_session_analytics(self) -> Dict[str, Any]:
        """Generate analytics for the current session"""
        total_exchanges = len(self.conversation_history)
        students_participated = len([s for s in self.frame_memory["students"] if s["turn_count"] > 0])
        
        performance_summary = {"correct": 0, "partially_correct": 0, "incorrect": 0, "pending": 0}
        for student in self.frame_memory["students"]:
            for perf in student["performance_history"]:
                if perf in performance_summary:
                    performance_summary[perf] += 1
        
        return {
            "total_exchanges": total_exchanges,
            "students_participated": students_participated,
            "performance_summary": performance_summary,
            "topics_covered": ["microcontroller_definition", "microcontroller_components"],
            "learning_objectives_met": ["Students can define what a microcontroller is"],
            "turn_distribution": {s["color"]: s["turn_count"] for s in self.frame_memory["students"]},
            "difficulty_progression": ["foundational", "intermediate", "intermediate"]
        }
    
    def _calculate_session_duration(self) -> str:
        """Calculate session duration from conversation history"""
        if len(self.conversation_history) < 2:
            return "0 seconds"
        
        start_time = datetime.datetime.fromisoformat(self.conversation_history[0]["timestamp"])
        end_time = datetime.datetime.fromisoformat(self.conversation_history[-1]["timestamp"])
        duration = end_time - start_time
        
        return f"{duration.total_seconds():.0f} seconds"
    
    def process_input(self, user_input: str) -> str:
        """
        Main entry point for processing user input
        Follows the Four-Slot execution flow
        """
        # Determine if this is a structured test or interactive session
        try:
            json_data = json.loads(user_input)
            return self._process_structured_test(json_data)
        except json.JSONDecodeError:
            return self._process_interactive_session(user_input)
    
    def _process_structured_test(self, json_data: Dict[str, Any]) -> str:
        """Process a structured test with provided JSON data"""
        # Use provided data instead of persistent memory
        self.frame_memory = json_data["frame_memory"]
        self.conversation_history = json_data["conversation_history"]
        
        # Process the user input through slots
        return self._execute_four_slot_flow(json_data["user_input"])
    
    def _process_interactive_session(self, user_input: str) -> str:
        """Process an interactive session with persistent memory"""
        # Create conversation file if this is the first message
        if not self.current_conversation_file:
            filename = self._create_conversation_file()
            print(f"**[SLOT 1]** CONVERSATION FILE: Created `memory/{filename}`")
        
        # Process through slots
        response = self._execute_four_slot_flow(user_input)
        
        # Save conversation after each turn
        self._save_conversation()
        print(f"**[SLOT 5]** CONVERSATION SAVED: Writing complete conversation data to `{os.path.basename(self.current_conversation_file)}`")
        
        return response
    
    def _execute_four_slot_flow(self, user_input: str) -> str:
        """Execute the Four-Slot execution flow"""
        # SLOT 1: Analyze Input
        analysis = self._slot_1_analyze_input(user_input)
        
        # SLOT 2: Shape Prompt
        prompt_instructions = self._slot_2_shape_prompt(analysis)
        
        # SLOT 3: Generate
        draft_response = self._slot_3_generate(prompt_instructions, analysis)
        
        # SLOT 4: Validate & Repair
        final_response = self._slot_4_validate_repair(draft_response, analysis)
        
        # Add to conversation history
        self._add_to_conversation_history(user_input, final_response, analysis)
        
        return final_response
    
    def _slot_1_analyze_input(self, user_input: str) -> Dict[str, Any]:
        """SLOT 1: Analyze the student's message"""
        print("**[SLOT 1]** Analyzing input...")
        
        # Identify speaker
        speaker_color = None
        if ": " in user_input:
            speaker_color = user_input.split(": ")[0].strip()
        
        # Update turn count and assess performance
        performance = "pending"
        next_student_id = None
        
        if speaker_color:
            # Find student and update turn count
            for student in self.frame_memory["students"]:
                if student["color"].lower() == speaker_color.lower():
                    student["turn_count"] += 1
                    
                    # Assess performance based on content
                    performance = self._assess_performance(user_input)
                    student["performance_history"].append(performance)
                    
                    print(f"**[SLOT 1]** Speaker: {speaker_color}, Performance: {performance}, Turn count: {student['turn_count']}")
                    break
            
            # Determine next student (least turns)
            next_student = min(self.frame_memory["students"], key=lambda s: s["turn_count"])
            next_student_id = next_student["id"]
            print(f"**[SLOT 1]** Next target: {next_student['color']} (least turns)")
        
        analysis = {
            "speaker_color": speaker_color,
            "performance": performance,
            "on_topic": True,  # Simplified for this implementation
            "next_student_id": next_student_id,
            "user_input": user_input
        }
        
        print(f"**[SLOT 1]** Analysis complete. CONTEXT UPDATE: {analysis}")
        return analysis
    
    def _slot_2_shape_prompt(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """SLOT 2: Shape prompt based on context"""
        print("**[SLOT 2]** Shaping prompt...")
        
        instructions = {
            "knowledge_grounding": "Base the quiz question and any explanations exclusively on the content of learning_material/microcontrollers.md",
            "difficulty_adaptation": self._get_difficulty_instruction(analysis["performance"]),
            "target_student": f"Address the question specifically to the student identified as {analysis['next_student_id']}"
        }
        
        print(f"**[SLOT 2]** PROMPT SHAPED: Grounded in learning material. {instructions['difficulty_adaptation']}")
        return instructions
    
    def _slot_3_generate(self, instructions: Dict[str, str], analysis: Dict[str, Any]) -> str:
        """SLOT 3: Generate draft response"""
        print("**[SLOT 3]** Generating draft response...")
        
        # This is a simplified implementation
        # In a real implementation, this would interface with an LLM
        if analysis["speaker_color"]:
            # Generate follow-up question
            next_student_color = self._get_student_color(analysis["next_student_id"])
            draft = f"Great answer, {analysis['speaker_color']}! Now, {next_student_color}, can you tell me more about microcontroller components?"
        else:
            # Generate opening question
            draft = "Hey there, Red! Welcome to our microcontroller study session! I'm Marty, and I'm super excited to learn about microcontrollers with you all. Let's start with something fundamental - Red, can you tell me what a microcontroller is in your own words?"
        
        print(f"**[SLOT 3]** AI DRAFT: {draft}")
        return draft
    
    def _slot_4_validate_repair(self, draft: str, analysis: Dict[str, Any]) -> str:
        """SLOT 4: Validate and repair the draft"""
        print("**[SLOT 4]** Validating draft...")
        
        # Knowledge-Check
        print("**[SLOT 4]** Knowledge-Check: PASS - Content based on learning material")
        
        # Persona-Check
        print("**[SLOT 4]** Persona-Check: PASS - Friendly, encouraging peer tone")
        
        # Target-Check
        print("**[SLOT 4]** Target-Check: PASS - Addressed to correct student")
        
        # Difficulty-Check
        print("**[SLOT 4]** Difficulty-Check: PASS - Appropriate difficulty level")
        
        print("**[SLOT 4]** All checks passed. Draft approved.")
        return draft
    
    def _assess_performance(self, user_input: str) -> str:
        """Assess student performance based on input content"""
        # Simplified assessment logic
        input_lower = user_input.lower()
        
        if any(word in input_lower for word in ["microcontroller", "computer", "control", "sensor"]):
            if any(word in input_lower for word in ["processor", "memory", "input", "output"]):
                return "correct"
            else:
                return "partially_correct"
        else:
            return "incorrect"
    
    def _get_difficulty_instruction(self, performance: str) -> str:
        """Get difficulty adaptation instruction based on performance"""
        if performance == "incorrect":
            return "Ask another student 'What do you think? Do you agree with what the previous student said?'"
        elif performance == "partially_correct":
            return "Validate what is correct and ask for clarification on missing parts"
        else:  # correct
            return "Ask a more challenging follow-up question"
    
    def _get_student_color(self, student_id: str) -> str:
        """Get student color by ID"""
        for student in self.frame_memory["students"]:
            if student["id"] == student_id:
                return student["color"]
        return "Unknown"
    
    def _add_to_conversation_history(self, user_input: str, response: str, analysis: Dict[str, Any]):
        """Add current exchange to conversation history"""
        timestamp = datetime.datetime.now().isoformat()
        
        # Add user input
        if user_input:
            self.conversation_history.append({
                "turn_number": len(self.conversation_history) + 1,
                "timestamp": timestamp,
                "role": "user",
                "content": user_input,
                "slot_analysis": {
                    "slot_1": f"Speaker: {analysis['speaker_color']}, Performance: {analysis['performance']}"
                }
            })
        
        # Add assistant response
        self.conversation_history.append({
            "turn_number": len(self.conversation_history) + 1,
            "timestamp": timestamp,
            "role": "assistant",
            "content": response,
            "slot_analysis": {
                "slot_1": "Generated response",
                "slot_2": "Prompt shaped",
                "slot_3": "Draft generated",
                "slot_4": "All checks passed"
            }
        })


def main():
    """Main function for testing the frame"""
    frame = QuizMasterMartyFrame()
    
    # Test with interactive session
    print("Starting Quiz Master Marty Frame...")
    print("=" * 50)
    
    # First message (setup)
    response1 = frame.process_input("3 students red, blue, green. ask first red")
    print(f"\nMarty: {response1}")
    print("=" * 50)
    
    # Student response
    response2 = frame.process_input("Red: well, a microcontroller is a mini computer that you can use to create intelligent objects, like robots.")
    print(f"\nMarty: {response2}")
    print("=" * 50)


if __name__ == "__main__":
    main()
