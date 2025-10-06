# Cognitive Engagement Partner Frame

## Frame Metadata
- **Frame ID**: `cognitive_engagement_partner`
- **Purpose**: To track academic tasks, detect student disengagement, and build motivational bridges by connecting tasks to student interests.
- **Category**: Motivational/Engagement & Task Management
- **Complexity**: Advanced (uses LLM-powered semantic analysis and memory management)

## What This Frame Does

This frame combines task tracking with motivational support. It has two main capabilities:

### 1. Task Tracking & Management
- **Detects new tasks**: When a student mentions an assignment or learning goal
- **Maintains focus**: Keeps the current task in memory throughout the conversation
- **Handles transitions**: Asks for confirmation before switching to a new task
- **Preserves history**: Stores completed tasks for context

### 2. Motivational Engagement
When disengagement is detected, the frame:
1. **Semantically analyzes** the student's message for signs of boredom or dismissiveness
2. **Infers student interests** from conversation history 
3. **Builds motivational bridges** connecting the current task to personal interests
4. **Invites engagement** through open-ended questions

## Architectural Note

**Modularity Consideration**: In a production system, task tracking could (and should) be implemented as a separate `TaskTracker` frame that works in combination with this `CognitiveEngagementPartner`. This would follow better separation of concerns:
- `TaskTracker`: Handles task detection, memory, and transitions
- `CognitiveEngagementPartner`: Focuses purely on motivation and interest-based bridges

This combined implementation serves as a prototype to demonstrate how frames can share context and memory effectively.

## Test Scenarios

- `test_scenarios/scenario_1_disengaged_no_memory.json`: Tests disengagement detection with no prior knowledge of interests
- `test_scenarios/scenario_2_disengaged_with_memory.json`: Tests disengagement detection when interests are already known
- `test_scenarios/scenario_3_task_switch.json`: Tests task switching confirmation when a student mentions a new assignment

## Usage

Create a custom mode/persona in your AI assistant (e.g., Custom Mode in Cursor AI, Custom Instructions in Claude Code, etc.), paste the content of `FRAME.md` into the instructions, then test using either JSON scenarios or interactive chat.
