#!/usr/bin/env python3
"""
Test Runner for Quiz Master Marty Frame

This script provides various ways to test the Quiz Master Marty frame implementation
"""

import json
import os
import sys
from pathlib import Path
from quiz_master_marty import QuizMasterMartyFrame


def test_structured_scenario():
    """Test with structured JSON scenario"""
    print("=" * 60)
    print("TESTING: Structured JSON Scenario")
    print("=" * 60)
    
    # Load test scenario
    test_file = Path(__file__).parent / "test_scenarios" / "three_students_quiz_scenario.json"
    
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return
    
    with open(test_file, 'r') as f:
        test_data = json.load(f)
    
    # Create frame instance
    frame = QuizMasterMartyFrame()
    
    # Process the test input
    json_input = json.dumps(test_data)
    response = frame.process_input(json_input)
    
    print(f"\nTest Input: {test_data['user_input']}")
    print(f"Marty Response: {response}")
    print("\nFrame Memory Updated:")
    print(json.dumps(frame.frame_memory, indent=2))


def test_interactive_session():
    """Test with interactive session"""
    print("=" * 60)
    print("TESTING: Interactive Session")
    print("=" * 60)
    
    frame = QuizMasterMartyFrame()
    
    # Simulate a conversation
    inputs = [
        "3 students red, blue, green. ask first red",
        "Red: well, a microcontroller is a mini computer that you can use to create intelligent objects, like robots. it allows to connect sensors and act depending on the sensory inputs autonomously.",
        "Blue: there are power inputs, sensory inputs, processor, and outputs",
        "Green: I think there's also memory and a clock inside"
    ]
    
    for i, user_input in enumerate(inputs, 1):
        print(f"\n--- Turn {i} ---")
        print(f"Input: {user_input}")
        
        response = frame.process_input(user_input)
        print(f"Marty: {response}")
        
        if i < len(inputs):
            print("\n" + "-" * 40)


def test_conversation_persistence():
    """Test conversation file creation and persistence"""
    print("=" * 60)
    print("TESTING: Conversation Persistence")
    print("=" * 60)
    
    frame = QuizMasterMartyFrame()
    
    # Start a new conversation
    response = frame.process_input("Red: A microcontroller is like a tiny computer")
    
    print(f"Marty: {response}")
    
    # Check if conversation file was created
    if frame.current_conversation_file:
        print(f"\nConversation file created: {os.path.basename(frame.current_conversation_file)}")
        
        # Read and display the file
        with open(frame.current_conversation_file, 'r') as f:
            conversation_data = json.load(f)
        
        print("\nConversation Data:")
        print(f"- Session ID: {conversation_data['conversation_id']}")
        print(f"- Total Exchanges: {conversation_data['session_analytics']['total_exchanges']}")
        print(f"- Students Participated: {conversation_data['session_analytics']['students_participated']}")
        print(f"- Performance Summary: {conversation_data['session_analytics']['performance_summary']}")
    else:
        print("No conversation file created!")


def test_performance_assessment():
    """Test student performance assessment"""
    print("=" * 60)
    print("TESTING: Performance Assessment")
    print("=" * 60)
    
    frame = QuizMasterMartyFrame()
    
    test_responses = [
        ("Red: A microcontroller is a small computer that controls devices", "correct"),
        ("Blue: It has a processor and memory", "partially_correct"),
        ("Green: I don't know what that is", "incorrect"),
        ("Red: It's like the brain of a washing machine", "correct")
    ]
    
    for response, expected in test_responses:
        assessed = frame._assess_performance(response)
        status = "✅ PASS" if assessed == expected else "❌ FAIL"
        print(f"{status} | Input: '{response}' | Expected: {expected} | Got: {assessed}")


def test_turn_management():
    """Test student turn management"""
    print("=" * 60)
    print("TESTING: Turn Management")
    print("=" * 60)
    
    frame = QuizMasterMartyFrame()
    
    # Simulate multiple turns
    inputs = [
        "Red: Microcontrollers are small computers",
        "Blue: They have processors and memory",
        "Green: They control devices",
        "Red: They work in loops"
    ]
    
    print("Initial turn counts:")
    for student in frame.frame_memory["students"]:
        print(f"  {student['color']}: {student['turn_count']}")
    
    print("\nProcessing turns...")
    for i, user_input in enumerate(inputs, 1):
        frame.process_input(user_input)
        
        print(f"\nAfter turn {i}:")
        for student in frame.frame_memory["students"]:
            print(f"  {student['color']}: {student['turn_count']} turns, performance: {student['performance_history']}")


def run_all_tests():
    """Run all test functions"""
    print("QUIZ MASTER MARTY FRAME - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    tests = [
        test_structured_scenario,
        test_interactive_session,
        test_conversation_persistence,
        test_performance_assessment,
        test_turn_management
    ]
    
    for test_func in tests:
        try:
            test_func()
            print("\n" + "=" * 80)
        except Exception as e:
            print(f"\n❌ Test {test_func.__name__} failed: {e}")
            print("=" * 80)
    
    print("\n🎉 All tests completed!")


def main():
    """Main function"""
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        
        if test_name == "structured":
            test_structured_scenario()
        elif test_name == "interactive":
            test_interactive_session()
        elif test_name == "persistence":
            test_conversation_persistence()
        elif test_name == "performance":
            test_performance_assessment()
        elif test_name == "turns":
            test_turn_management()
        elif test_name == "all":
            run_all_tests()
        else:
            print(f"Unknown test: {test_name}")
            print("Available tests: structured, interactive, persistence, performance, turns, all")
    else:
        print("Quiz Master Marty Frame Test Runner")
        print("Usage: python test_runner.py <test_name>")
        print("\nAvailable tests:")
        print("  structured  - Test with JSON scenario")
        print("  interactive - Test interactive session")
        print("  persistence - Test conversation file creation")
        print("  performance - Test performance assessment")
        print("  turns       - Test turn management")
        print("  all         - Run all tests")


if __name__ == "__main__":
    main()
