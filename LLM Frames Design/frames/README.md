# How to Prototype a Rodin Frame

This directory allows you to design and test new Rodin "Frames"—the rules that guide the AI—using only natural language. The process is designed to be accessible to domain experts, like educators, without requiring any coding.

### Fast Prototyping Workflow

For the quickest iteration, you can use your AI assistant as a collaborative partner.

1.  **AI-Assisted Creation**: Instead of writing the `FRAME.md` from scratch, you can add the `_TEMPLATE/FRAME.md` file to your AI assistant's context and have a conversation to define your new Frame. For example: "Let's create a Socratic tutor. It should ask probing questions and never give direct answers. Let's start with the persona..."
2.  **Quick Testing**: To quickly test any `FRAME.md`, add it to the context window and tell your assistant to adopt that persona. For example: "Behave exactly like the instructions in the attached `FRAME.md` file." This bypasses the need to formally create a custom mode for a quick test.

### The Formal Workflow

For a more manual approach, follow this 3-step process:

1.  **Create**: Copy the `_TEMPLATE/` directory and rename it to describe your new Frame (e.g., `socratic_method`). The name should be `lower_snake_case`.
2.  **Define**: Open the `FRAME.md` file inside your new directory. This file is the "brain" of your prototype. Follow the instructions inside to define how your frame should think and act.
3.  **Test**:
    *   **Set up your AI assistant**: Use its feature for custom instructions or personas (e.g., "Custom Modes" in Cursor AI).
    *   **Load the Frame's "brain"**: Paste the entire content of your `FRAME.md` file into the custom instructions.
    *   **Start testing**:
        *   **Interactive test**: Start a conversation. The AI will use `memory/memory.json` to remember context, for example, depending on instructions in the `FRAME.md` file.
        *   **Repeatable test**: See the "Writing and Running Repeatable Tests" section below.

### Writing and Running Repeatable Tests

For consistent testing, you can create structured test scenarios in a JSON file. This allows you to test exactly how your Frame responds to a specific situation, making it easy to check for regressions as you make changes.

1.  **Create a JSON File**: In your Frame's `test_scenarios/` directory, create a new `.json` file.
2.  **Define the Scenario**: The JSON object could have three keys, depending on the Frame:
    *   `user_input` (string): The exact message from the user for this turn.
    *   `conversation_history` (array): A list of previous messages to simulate a dialogue history. Each message is an object with a `role` ("assistant" or "user") and `content` (the message string).
    *   `frame_memory` (object): A snapshot of the Frame's memory state just before the `user_input` is processed.
3.  **Run the Test**: Copy the entire content of your JSON file and paste it into the chat with your AI assistant (after you have loaded the `FRAME.md` into its custom instructions). The assistant will perform a single run based on this exact scenario.

### Frame Capabilities

A Frame can be instructed to have access to key information like:

- **Current Message**: The student's latest input
- **Conversation History**: All previous messages in the dialogue
- **Persistent Memory**: Information your Frame can store and retrieve across multiple turns (e.g., student interests, preferences, learning patterns)
- **Turn Context**: Temporary state that other Frames can share within a single turn
