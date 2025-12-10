# Problem Solving Log

**Last Updated:** Dec 10th 2025

**Instructions for Updating:**
*   Do not replace or delete issues or their analysis, only add. You can only modify status. Keep them in the log for historical reference.
*   When a large issue is broken down into smaller, more specific problems, use a sub-numbering scheme (e.g., Issue 1.1, Issue 1.2).
*   Follow the structure for each issue: Problem, Root Cause Analysis, Solutions Applied, Status.

---

## Issue 1: Phase Time Management & Reporting (From Dec 9)
*   **Problem:** The `MnemonicCoCreatorFrame` is not switching phases correctly, the session is not closing after 10 minutes, and the final report is incomplete.
*   **Root Cause Analysis:** Previous analysis incorrectly pointed to a fatal crash in `core.py`. This theory has been disproven by new session logs where all report files were generated. The root cause is still unknown.
*   **Solutions Applied:** 
    *   Investigated `marty.py` phase transition logic.
    *   Analyzed old session logs.
*   **Status:** **Actively Under Investigation.**

### Issue 1.1: Incorrect LLM Instructions in Phase 3
*   **Problem:** Marty was reported to be giving Phase 2 instructions (e.g., "do you want to try 
adding the next two lines") during Phase 3.The conversation shows that students are still adding 
to and building the mnemonic after the 7-minute mark. After 10 minutes, Marty gives Phase 2 instructions (e.g., "can you help us with the final line") during Phase 3, instead of focusing on recall.
*   **Root Cause Analysis (Verified):** First: The `PhasesCheckerFrame` (the frame responsible for enforcing phase rules) disables its validation logic when the session's elapsed time is over 10 minutes (`_closure_ready` is true). This allows the LLM, which is incorrectly generating "creative" prompts, to operate unchecked during the final minutes of the session. Then: The `PhasesCheckerFrame` (the frame responsible for enforcing phase rules) and `BalancedTurnsFrame` both contain logic to disable their validation when `_closure_ready` becomes true after 10 minutes. This was confirmed with a `DEBUG` log run, which showed the log message `[PhasesChecker] Closure mode detected - passing validation` immediately after a non-compliant LLM response was generated. This allows the LLM, which is failing to adhere to the initial "recall-only" prompt, to operate without correction.
*   **Solutions Applied:** 
    *   Analyzed terminal logs which show the LLM generating "add to the poem" prompts during 
    Phase 3.
    *   Traced the logic to the `PhasesCheckerFrame`'s "closure mode" bypass.
    Modified `phases_checker.py` to remove the validation bypass.
    *   Implemented a custom validation logic for closure mode that checks for "creative" keywords and provides specific feedback to the LLM to guide it towards a session-ending response.
*   **Status:** **Retesting.**

### Issue 1.2: Session Closure Not Triggering
*   **Problem:** The session does not automatically close after the 10-minute mark.
*   **Root Cause Analysis:** Unknown.
*   **Solutions Applied:** 
    *   **Attempt 1 (Incorrect):** A hypothesis was formed that the `_closure_done` flag was being set prematurely in `_get_phase_2_instructions`. The logic was removed from that method on Dec 10.
    *   **Attempt 1 Reverted:** This change was incorrect and has been reverted. The root cause is still under investigation.
*   **Status:** **Actively Under Investigation.**

### Issue 1.3: Incomplete Markdown Reports
*   **Problem:** The "Phase Transitions" summary, which should be generated from `_phase_transitions` in memory, is completely missing from the final Markdown report.
*   **Root Cause Analysis:** Unknown. This points to an issue in `_save_markdown_report` where it fails to read or write this specific piece of data from the final `frame_memory`.
*   **Solutions Applied:** None yet.
*   **Status:** **Actively Under Investigation.**

### Issue 1.4: Missing JSON Prompts File
*   **Problem:** The `_prompts.json` file is not being generated at 
the end of a session.
*   **Root Cause Analysis:** This is a direct consequence of the 
crash in `_save_markdown_report` (Issue 1.3), as the JSON file is 
saved after the Markdown file.
*   **Solutions Applied:** Unknown
*   **Status:** **Resolved (Dec 9).**

### Issue 1.6: Marty Fails to Recite Mnemonic on Request
*   **Problem:** In Phase 3, when students are struggling and explicitly ask for the full mnemonic, Marty deflects instead of providing it.
*   **Root Cause Analysis (Verified):** First idea: The LLM prompt in `_get_phase_3_instructions` for handling stuck  students does not have a specific instruction for when a student directly asks for the answer. The LLM defaults to the generic "redirect" behavior instead of reciting the poem. Now: The `DEBUG` log run confirmed that the system prompt in `_get_phase_3_instructions` lacks a specific instruction for when a student directly asks for the answer. The LLM therefore defaults to its generic "redirect" behavior.
*   **Solutions Applied:** 
    *  Analyzed terminal logs showing a student asking for the poem and Marty deflecting.
    *   Reviewed the `_get_phase_3_instructions` prompt and identified the missing instruction.
    A new rule was added to the `_get_phase_3_instructions` method in `marty.py`: `IF a student asks to be reminded of the {general_label_lower} (e.g., "what do we have so far?", "remind me"): → RECITE the full {type_label_lower} and ask another student to continue.`
*   **Status:** **Resolved.**

---

## Issue 2: `TypeError` in `_get_phase_2_instructions` (From Dec 9)
*   **Problem:** Previous session logs indicated a `TypeError` due to a mismatched number of arguments.
*   **Root Cause Analysis:** The error was present in an older version of the code.
*   **Solutions Applied:** Analyzed the current `marty.py` file to confirm the function signature is now correct.
*   **Status:** **Resolved (Dec 9).**
