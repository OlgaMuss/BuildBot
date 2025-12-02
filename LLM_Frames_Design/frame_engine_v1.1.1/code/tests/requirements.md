# Test Requirements

This document defines the user stories that drive our test suite. Each user story maps to one or more test functions.

## Setup

Before running tests, create a `.env` file in this directory:

```bash
# tests/.env
GOOGLE_API_KEY="your-google-api-key-here"
```

Then run:

```bash
cd code/
poetry install
poetry run python -m pytest
```

---

## US1: Frame Pipeline Execution

**As a** developer using the Frame Engine  
**I want** all frames to execute their slots in the correct order  
**So that** the pipeline produces predictable, consistent results

### Acceptance Criteria
- Slot 1 (analyze_input) runs for all frames before Slot 2
- Slot 2 (get_prompt_sections + shape_prompt) accumulates prompts correctly
- Slot 3 (generate) calls the LLM with the assembled prompt
- Slot 4 (validate_output) runs for all frames concurrently

**Tests:** `test_engine.py::test_pipeline_executes_all_slots`, `test_engine.py::test_multiple_frames_compose`

---

## US2: Validation Loop

**As a** developer building guardrail frames  
**I want** the validation loop to handle PASS, REVISE, and FAIL actions correctly  
**So that** responses are either approved, regenerated with feedback, or safely aborted

### Acceptance Criteria
- PASS from all frames → response is returned
- REVISE from any frame → LLM is called again with feedback
- FAIL from any frame → fallback response is returned
- Max repair attempts (2) prevents infinite loops

**Tests:** `test_engine.py::test_validation_pass`, `test_engine.py::test_validation_revise`, `test_engine.py::test_validation_fail`

---

## US3: Prompt Section Accumulation

**As a** developer composing multiple frames  
**I want** each frame's prompt sections to be accumulated in order  
**So that** the final prompt contains contributions from all frames

### Acceptance Criteria
- Sections from multiple frames are joined with double newlines
- Section labels are optional (controlled by `include_section_labels`)
- Empty sections are ignored

**Tests:** `test_engine.py::test_prompt_accumulation`, `test_engine.py::test_prompt_with_labels`

---

## US4: Turn-Taking Management

**As a** facilitator using the Marty frame  
**I want** the system to track participation and suggest fair turn-taking  
**So that** all students have equal opportunity to contribute

### Acceptance Criteria
- Contribution count is tracked per student
- Speaking time is estimated from message length
- Recent speakers (last 5) are tracked
- Underparticipating students are identified
- Next speaker is suggested based on fairness criteria
- Monopolization (3+ consecutive turns) triggers a warning

**Tests:** `test_marty.py::test_participation_tracking`, `test_marty.py::test_turn_taking_suggestion`, `test_marty.py::test_monopolization_detection`, `test_marty.py::test_underparticipation_detection`

---

## US5: Session Phase Transitions

**As a** facilitator using the Marty frame  
**I want** the session to progress through phases based on turn count  
**So that** the pedagogical flow adapts appropriately

### Acceptance Criteria
- Phase 1 (turns 1-5): Knowledge Building
- Phase 2 (turns 6-20): Mnemonic Co-Creation
- Phase 3 (turns 21+): Memorization & Practice
- Phase boundaries are configurable via `phase_config`

**Tests:** `test_marty.py::test_phase_transitions`

---

## US6: Per-Concept Comprehension Tracking

**As a** facilitator using the ComprehensionTrackerFrame  
**I want** the system to track comprehension at the concept level per student  
**So that** I can identify specific misconceptions and avoid repeating well-understood concepts

### Acceptance Criteria
- Concepts are automatically extracted from learning material at session start
- Each student message is analyzed for concept mentions
- For each mentioned concept, a triplet is recorded: (concept, level, justification)
- Levels are: `NOT_SEEN`, `UNDERSTOOD`, `CONFUSED`, `MISCONCEPTION`
- Comprehension is tracked per student individually
- Assessments are updated at each turn
- Prompt sections include concepts to clarify and concepts to skip
- Well-understood concepts are tracked to avoid repetition

**Tests:** `test_comprehension_tracker.py::test_concept_extraction`, `test_comprehension_tracker.py::test_comprehension_assessment`, `test_comprehension_tracker.py::test_per_student_tracking`, `test_comprehension_tracker.py::test_prompt_sections_generated`

---

## US7: Focus Management

**As a** facilitator using the Marty frame  
**I want** the system to detect off-topic conversations and redirect  
**So that** the discussion stays productive

### Acceptance Criteria
- Off-topic messages are detected via LLM analysis
- Consecutive off-topic turns are counted
- After 2+ off-topic turns, redirection instruction is added to prompt

**Tests:** `test_marty.py::test_off_topic_detection`, `test_marty.py::test_redirection_after_off_topic`

---

## US8: LLM Provider Configuration

**As a** developer deploying the Frame Engine  
**I want** to configure different LLM providers via config.yaml  
**So that** I can switch between Google, OpenAI, and Anthropic

### Acceptance Criteria
- Provider is specified in config.yaml (`llm.provider`)
- Model name is configurable (`llm.model_name`)
- Missing API key raises `LLMConfigError` with clear message
- Temperature is optional

**Tests:** `test_llm.py::test_llm_provider_google`, `test_llm.py::test_llm_missing_api_key`, `test_llm.py::test_llm_unsupported_provider`, `test_llm.py::test_llm_temperature_optional`, `test_llm.py::test_llm_simple_call`

---

## Test Matrix

| User Story | Test File | Test Function(s) |
|------------|-----------|------------------|
| US1 | test_engine.py | `test_pipeline_executes_all_slots`, `test_multiple_frames_compose` |
| US2 | test_engine.py | `test_validation_pass`, `test_validation_revise`, `test_validation_fail` |
| US3 | test_engine.py | `test_prompt_accumulation`, `test_prompt_with_labels` |
| US4 | test_marty.py | `test_participation_tracking`, `test_turn_taking_suggestion`, `test_monopolization_detection`, `test_underparticipation_detection` |
| US5 | test_marty.py | `test_phase_transitions` |
| US6 | test_comprehension_tracker.py | `test_concept_extraction`, `test_comprehension_assessment`, `test_per_student_tracking`, `test_prompt_sections_generated` |
| US7 | test_marty.py | `test_off_topic_detection`, `test_redirection_after_off_topic` |
| US8 | test_llm.py | `test_llm_provider_google`, `test_llm_missing_api_key`, `test_llm_unsupported_provider`, `test_llm_temperature_optional`, `test_llm_simple_call` |

