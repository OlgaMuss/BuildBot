#!/usr/bin/env python3
"""
Command Line Interface for Quiz Master Marty Frame

This provides an interactive command-line interface for testing the frame
"""

import json
import sys
from quiz_master_marty import QuizMasterMartyFrame


class QuizMasterCLI:
    """Command Line Interface for Quiz Master Marty"""
    
    def __init__(self):
        self.frame = QuizMasterMartyFrame()
        self.running = True
        
    def print_help(self):
        """Print help information"""
        print("\n" + "="*60)
        print("QUIZ MASTER MARTY - Interactive CLI")
        print("="*60)
        print("Commands:")
        print("  help, h     - Show this help message")
        print("  status      - Show current frame status")
        print("  students    - Show student information")
        print("  memory      - Show frame memory")
        print("  clear       - Clear conversation history")
        print("  test        - Run test scenario")
        print("  quit, q     - Exit the program")
        print("\nTo interact with Marty, just type your message!")
        print("Format: 'Color: message' (e.g., 'Red: A microcontroller is...')")
        print("="*60)
    
    def print_status(self):
        """Print current frame status"""
        print("\n📊 FRAME STATUS")
        print("-" * 30)
        print(f"Conversation File: {self.frame.current_conversation_file or 'None'}")
        print(f"Total Exchanges: {len(self.frame.conversation_history)}")
        print(f"Quiz Topic: {self.frame.frame_memory['quiz_topic']}")
        
        print("\n👥 STUDENTS")
        print("-" * 30)
        for student in self.frame.frame_memory["students"]:
            perf_summary = ", ".join(student["performance_history"][-3:]) or "None"
            print(f"{student['color']:>5}: {student['turn_count']:2} turns | Recent: {perf_summary}")
    
    def print_students(self):
        """Print detailed student information"""
        print("\n👥 STUDENT DETAILS")
        print("-" * 50)
        for student in self.frame.frame_memory["students"]:
            print(f"\n{student['color']} Student:")
            print(f"  ID: {student['id']}")
            print(f"  Turns: {student['turn_count']}")
            print(f"  Performance History: {student['performance_history']}")
    
    def print_memory(self):
        """Print frame memory"""
        print("\n🧠 FRAME MEMORY")
        print("-" * 30)
        print(json.dumps(self.frame.frame_memory, indent=2))
    
    def clear_conversation(self):
        """Clear conversation history"""
        self.frame.conversation_history = []
        self.frame.current_conversation_file = None
        print("✅ Conversation history cleared")
    
    def run_test_scenario(self):
        """Run a test scenario"""
        print("\n🧪 RUNNING TEST SCENARIO")
        print("-" * 40)
        
        test_inputs = [
            "Red: A microcontroller is a small computer that controls devices",
            "Blue: It has a processor, memory, and input/output pins",
            "Green: It works by reading inputs, processing them, and controlling outputs"
        ]
        
        for i, test_input in enumerate(test_inputs, 1):
            print(f"\n--- Test Turn {i} ---")
            print(f"Input: {test_input}")
            
            response = self.frame.process_input(test_input)
            print(f"Marty: {response}")
    
    def process_user_input(self, user_input: str):
        """Process user input through the frame"""
        try:
            response = self.frame.process_input(user_input)
            print(f"\n🤖 Marty: {response}")
        except Exception as e:
            print(f"\n❌ Error processing input: {e}")
    
    def run(self):
        """Main CLI loop"""
        print("🤖 Welcome to Quiz Master Marty!")
        print("Type 'help' for commands or start chatting with Marty!")
        
        while self.running:
            try:
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.lower() in ['quit', 'q', 'exit']:
                    self.running = False
                    print("👋 Goodbye!")
                
                elif user_input.lower() in ['help', 'h']:
                    self.print_help()
                
                elif user_input.lower() == 'status':
                    self.print_status()
                
                elif user_input.lower() == 'students':
                    self.print_students()
                
                elif user_input.lower() == 'memory':
                    self.print_memory()
                
                elif user_input.lower() == 'clear':
                    self.clear_conversation()
                
                elif user_input.lower() == 'test':
                    self.run_test_scenario()
                
                else:
                    # Process as regular input
                    self.process_user_input(user_input)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                self.running = False
            except EOFError:
                print("\n\n👋 Goodbye!")
                self.running = False
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")


def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Quiz Master Marty CLI")
        print("Usage: python cli.py")
        print("\nThis provides an interactive command-line interface")
        print("for testing the Quiz Master Marty frame.")
        return
    
    cli = QuizMasterCLI()
    cli.run()


if __name__ == "__main__":
    main()
