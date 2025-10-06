A test scenario is a JSON file that defines the exact context your Frame will operate on. This allows you to create repeatable tests for specific situations.

The JSON file has the same structure as the `FrameContext` object in the design specifications:

-   `user_input`: (string) The student's most recent message.
-   `conversation_history`: (array of objects) A list of previous messages, simulating a longer dialogue.
-   `frame_memory`: (object) The state of your frame's persistent memory *before* the test runs.

By creating different JSON files, you can test how your Frame behaves in various situations (e.g., with an empty memory vs. a pre-populated memory).
