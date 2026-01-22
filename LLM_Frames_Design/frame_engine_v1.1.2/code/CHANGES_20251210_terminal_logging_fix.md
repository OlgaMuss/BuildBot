# Changes - December 10, 2025: Terminal Logging Fix & Circular Import Resolution

**Date:** 2025-12-10  
**Version:** frame_engine_v1.1.2  
**Author:** Olga

-----

**Topic:** Fixes for Closure Logic Loop & Recall Phase Guardrails

**Overview**
I’ve pushed updates to `phases_checker.py` and `marty.py`. The primary goal was to fix the issue where the bot wouldn't properly end the session (closure loop) and to add stricter guardrails during the mnemonic recall phase.

### 1\. `src/backend/frames/phases_checker.py`

**Change:** Removed the "auto-pass" logic for the closure phase. Previously, if `_closure_ready` was set, we skipped validation. Now, we explicitly validate the closing message to ensure it contains a goodbye and doesn't invite further discussion.

**Code Diff:**

```python
# REMOVED (The early return that was causing loose closures)
- # Check if session is in closure mode - if so, pass validation
- if frame_memory.get('_closure_ready'):
-     logging.info("[PhasesChecker] Closure mode detected - passing validation")
-     return {'action': ValidationAction.PASS, 'feedback': None}

# ADDED (Strict validation logic inside the compliance check)
 if not is_compliant:
-    detailed_feedback = _POLICY_VIOLATION_FEEDBACK
+    if frame_memory.get('_closure_ready'):
+        detailed_feedback = (
+            "The session is ending. Your response was not a valid closing message. "
+            "YOUR FINAL RESPONSE MUST:\n"
+            "1. Thank ALL students by name for their contributions and mention that our session time is up.\n"
+            "2. Celebrate what the group accomplished together.\n"
+            "3. Encourage them to keep practicing or share their favorite part.\n"
+            "4. Offer a friendly goodbye to everyone. Do NOT invite another student to speak."
+        )
+        logging.warning("[PhasesChecker] Closure validation failed. Response: '%s'", context['llm_draft_response'])
+    else:
+        detailed_feedback = _POLICY_VIOLATION_FEEDBACK
```

### 2\. `src/backend/frames/marty.py`

**Change:** Updated the Phase 2 prompt generation to handle "Recall Only Mode." If a student tries to add new concepts during the final testing phase, the bot is now explicitly instructed to reject it and redirect to reciting.

**Code Diff:**

```python
# Updated signature to accept context
- def _get_phase_2_instructions(self, mnemonic_state: dict[str, Any], frame_memory: dict[str, Any]) -> str:
+ def _get_phase_2_instructions(self, mnemonic_state: dict[str, Any], frame_memory: dict[str, Any], context: FrameContext) -> str:

# Added Prompt Guardrails
  Testing memory is the ONLY goal now.
  
+ IF a student asks to be reminded of the {general_label_lower} (e.g., "what do we have so far?", "remind me"):
+ → RECITE the full {type_label_lower} and ask another student to continue.
+
  IF a student asks a question or tries to add to the {general_label_lower}:
  → DO NOT ANSWER or ACCEPT IT.
```