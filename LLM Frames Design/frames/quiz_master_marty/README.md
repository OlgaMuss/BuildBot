# Quiz Master Marty Frame

## Overview
Quiz Master Marty is a Rodin Frame Simulator designed to simulate a social robot conducting oral discussions with 3-4 students about microcontrollers. The frame uses a Four-Slot execution flow to process student responses and generate appropriate follow-up questions.

## Purpose
- **Educational Assessment**: Conduct 15-minute oral discussion sessions (5 minutes per student)
- **Student Engagement**: Maintain friendly, encouraging peer persona
- **Knowledge Tracking**: Monitor student performance and turn-taking
- **Adaptive Difficulty**: Adjust questions based on student responses

## Key Features
- **Four-Slot Execution Flow**: Analyze → Shape → Generate → Validate & Repair
- **Conversation Persistence**: Creates timestamped conversation files
- **Student Tracking**: Monitors turn counts and performance history
- **Knowledge Grounding**: All content based on learning material
- **Oral Discussion Format**: Designed for conversational assessment

## File Structure
```
quiz_master_marty/
├── FRAME.md                                    # Main frame instructions
├── README.md                                   # This file
├── learning_material/
│   ├── microcontrollers.md                     # Knowledge source
│   ├── microcontroller_knowledge_points_14_15yo.md  # Learning objectives
│   └── question_bank_microcontrollers.md       # Discussion prompts
├── memory/
│   ├── memory.json                            # Default frame memory
│   ├── conversation_YYYY-MM-DD_HH-MM-SS.json  # Generated conversation files
│   └── conversation_YYYY-MM-DD_HH-MM-SS.md    # Human-readable logs
└── test_scenarios/
    └── three_students_quiz_scenario.json      # Test data
```

## Usage
1. **Create Custom Mode**: Copy FRAME.md content into AI assistant custom mode
2. **Test with JSON**: Use test_scenarios for structured testing
3. **Interactive Session**: Start with simple string input for live conversation
4. **Review Results**: Check generated conversation files for analysis

## Target Audience
- **Students**: 14-15 year olds learning about microcontrollers
- **Educators**: Teachers conducting oral assessments
- **Researchers**: Studying conversational AI in education

## Assessment Method
- **Format**: Oral discussion (no written materials)
- **Duration**: 15 minutes total (5 minutes per student)
- **Focus**: Understanding demonstration through conversation
- **Scoring**: 4-point rubric (Excellent/Good/Satisfactory/Needs Improvement)
