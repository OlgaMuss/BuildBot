# Variables for Pre-registration Analysis

This document outlines the variables identified for analysis in the context of the Microcontrollers learning session. These variables are primarily extracted from the session data (`session_Microcontrollers_20251210_133400.yaml`) and the learning material (`session_Microcontrollers_20251210_133400.md`).

## 1. Session Metadata

*   **`session_id`**: Unique identifier for each session (e.g., `Microcontrollers_20251210_133400`).
*   **`saved_at`**: Timestamp indicating when the session data was recorded.
*   **`metadata.topic`**: The main subject of the session (e.g., "Microcontrollers").
*   **`metadata.mnemonic_type`**: The type of mnemonic strategy employed (e.g., "Poem").
*   **`metadata.students`**: A list of student participants involved in the session (e.g., "Red", "Green", "Blue").
*   **`metadata.target_age`**: The age group for which the learning material and session were designed (e.g., 14).
*   **`frame_memory.session_start_time`**: The precise start time of the session.
*   **`frame_memory.elapsed_time_minutes`**: The total duration of the session in minutes.

## 2. Interaction and Turn-Taking Metrics

*   **`events.turn_count`**: The sequential count of turns within the conversation.
*   **`events.speaker`**: Identifies the participant speaking in each turn (e.g., "Red", "Green", "Blue", "assistant").
*   **`events.contribution_type`**: Categorizes the nature of a student's contribution (e.g., "mnemonic_suggestion", "knowledge_statement", "builds_on_idea", "recall_attempt").
*   **`events.is_relevant`**: A boolean flag indicating whether a student's contribution was relevant to the topic.
*   **`events.off_topic_duration`**: Measures the duration (in seconds) that a conversation deviates from the main topic.
*   **`events._suggested_next_speaker`**: The AI's suggestion for the next speaker, aimed at balancing participation.
*   **`events._consecutive_same_speaker`**: Tracks consecutive turns by the same speaker.
*   **`events.data.underparticipating_students`**: A list of students identified as having lower participation.
*   **`frame_memory.balanced_turns_validator.participation.contribution_count`**: The total number of contributions made by each student.
*   **`frame_memory.balanced_turns_validator.participation.total_speaking_time_seconds`**: The cumulative speaking time for each student.
*   **`frame_memory.balanced_turns_validator.participation.last_contribution_time`**: Timestamp of each student's most recent contribution.

## 3. Content and Comprehension

*   **`events.data.message` / `events.data.user`**: The actual textual content of student inputs.
*   **`events.data.assistant`**: The textual responses provided by the AI assistant.
*   **`events.data.mnemonic_progress`**: A narrative summary of the progress in developing the mnemonic device.
*   **`events.data.summary`**: A brief summary of the student's message in each turn.
*   **`frame_memory.comprehension_tracker.concepts`**: A comprehensive list of all concepts discussed and tracked throughout the session.
*   **`events.data.per_turn_analysis.understood`**: Concepts that were identified as understood by students in a particular turn.
*   **`events.data.per_turn_analysis.confused`**: Concepts that were identified as confusing for students in a particular turn.
*   **`events.data.cumulative_assessments_updated.concept`**: The specific concept being evaluated.
*   **`events.data.cumulative_assessments_updated.level`**: The assessed comprehension level of a concept (e.g., "UNDERSTOOD").
*   **`events.data.cumulative_assessments_updated.justification`**: The reasoning or evidence supporting the assigned comprehension level.

## 4. Mnemonic Creation Process

*   **`events.session_phase`**: Indicates the current stage of the session (e.g., Phase 1: concept generation, Phase 2: mnemonic construction, Phase 3: recall).
*   **`frame_memory.mnemonic_state.selected_concepts`**: The set of concepts chosen for inclusion in the mnemonic device.
*   **`frame_memory.mnemonic_state.concepts_finalized`**: A boolean indicating whether the selection of concepts for the mnemonic has been completed.
*   **`frame_memory.mnemonic_state.mnemonic_text`**: The final, complete text of the created mnemonic device.
*   **`frame_memory.mnemonic_state.mnemonic_created`**: A boolean flag confirming the successful creation of the mnemonic.
*   **`frame_memory.mnemonic_state._quality_validated`**: Indicates if the quality of the mnemonic was formally assessed.
*   **`frame_memory.mnemonic_state._quality_passed`**: A boolean indicating whether the mnemonic passed the quality assessment.
*   **`frame_memory.mnemonic_state._quality_feedback`**: Any feedback received regarding the quality of the mnemonic.

## 5. Recall Performance

*   **`frame_memory.recall_tracking.<student_name>.attempts`**: The number of times each student attempted to recall the mnemonic.
*   **`frame_memory.recall_tracking.<student_name>.successful_parts`**: The portions of the mnemonic that each student successfully recalled.
*   **`frame_memory.recall_tracking.<student_name>.stuck_on`**: The specific parts of the mnemonic where each student encountered difficulties during recall.
*   **`frame_memory.recall_tracking.<student_name>.last_attempt`**: The content of the last recall attempt made by each student.

## 6. System Feedback and Validation

*   **`events.data.feedback`**: Messages generated by the validation frames (e.g., `TURN-TAKING ERROR`, `The response did not adhere to the Phase Goal`).
*   **`events.data.action`**: The action recommended by a validator (e.g., "pass", "revise").
