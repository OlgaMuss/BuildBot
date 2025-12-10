# Changes - December 10, 2025: Terminal Logging Fix & Circular Import Resolution

**Date:** 2025-12-10  
**Version:** frame_engine_v1.1.2  
**Author:** Olga

---

## Summary

Fixed terminal logging to properly capture Python logging output (INFO, WARNING, ERROR messages) and integrate it into the main session markdown report. Resolved circular import between `marty.py` and `balanced_turns.py` that was preventing the system from starting.

---

## Problem Statement

1. **Empty Terminal Log Files**: The `session_{id}_terminal_log.md` files were being created but remained empty because Python's `logging` module output wasn't being captured.

2. **Circular Import Error**: `ImportError: cannot import name 'SPEAKER_KEY' from partially initialized module 'backend.frames.marty'` due to mutual imports between `marty.py` and `balanced_turns.py`.

3. **Duplicate Logging**: Log messages appeared 3x in terminal output due to multiple `FileHandler` instances accumulating.

4. **Orphan Files**: Temporary `_terminal_log.md` files were left behind from incomplete sessions.

---

## Solution Overview

### 1. Terminal Logging Integration
- Capture both `sys.stdout`/`sys.stderr` AND Python's `logging` module output
- Write to temporary file during session
- Integrate content into main markdown report when session ends
- Delete temporary file after integration
- Result: **One `.md` file per session** with integrated system log

### 2. Circular Import Fix
- Remove mutual imports between `marty.py` and `balanced_turns.py`
- Each frame uses string literals when reading from `shared_context`
- Each frame defines its own constants when writing to `shared_context`
- Result: **No circular dependencies**, clean import order

---

## Detailed Changes

### File 1: `scripts/frontend.py`

**Lines 32:** Added import
```python
from backend.frame_engine.core import SessionLogger, TerminalLogger
```

**Lines 136-166:** Terminal logging setup (after session initialization)
```python
# Setup terminal logging to capture Python logging output
sessions_dir = project_root / 'sessions'
sessions_dir.mkdir(exist_ok=True)

# Clean up any leftover terminal log files from previous sessions
for old_log in sessions_dir.glob('*_terminal_log.md'):
    try:
        old_log.unlink()
    except Exception:
        pass

terminal_log_path = sessions_dir / f"session_{session_id}_terminal_log.md"
shared_log_file = open(terminal_log_path, 'w', encoding='utf-8')
sys.stdout = TerminalLogger(str(terminal_log_path), stream=sys.stdout, shared_file=shared_log_file)
sys.stderr = TerminalLogger(str(terminal_log_path), stream=sys.stderr, shared_file=shared_log_file)

# Remove any old FileHandlers to prevent duplicate logging
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):
        handler.close()
        root_logger.removeHandler(handler)

# Capture Python logging module output to same file
log_handler = logging.FileHandler(terminal_log_path, mode='a')
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
root_logger.addHandler(log_handler)

session_logger._shared_log_file = shared_log_file
session_logger._log_handler = log_handler
```

**Purpose:**
- Redirect stdout/stderr through `TerminalLogger`
- Add `FileHandler` to capture Python logging to same file
- Remove old handlers to prevent 3x duplication
- Clean up orphan files from previous sessions

---

### File 2: `src/backend/frame_engine/core.py`

**Lines 562-602:** Integration logic in `SessionLogger.save()`
```python
# --- Append Terminal Log Content ---
if hasattr(self, '_shared_log_file') and self._shared_log_file:
    # Remove logging handler and flush/close the terminal log file
    if hasattr(self, '_log_handler') and self._log_handler:
        try:
            self._log_handler.flush()
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler.close()
        except Exception:
            pass
    
    try:
        self._shared_log_file.flush()
        self._shared_log_file.close()
    except Exception:
        pass
    
    # Read the terminal log content
    terminal_log_path = self.output_dir / f"session_{self.session_id}_terminal_log.md"
    if terminal_log_path.exists():
        terminal_content = terminal_log_path.read_text(encoding='utf-8')
        if terminal_content.strip():
            f.write("## 🖥️ System Log\n\n")
            f.write("```\n")
            f.write(terminal_content)
            f.write("```\n\n")
        
        # Delete the separate terminal log file
        try:
            terminal_log_path.unlink()
        except Exception:
            pass
        
        # Also clean up any orphan terminal log files from incomplete sessions
        for orphan_log in self.output_dir.glob('*_terminal_log.md'):
            try:
                orphan_log.unlink()
            except Exception:
                pass
```

**Purpose:**
- Close and flush handlers before reading
- Read terminal log content
- Append to main markdown report under "🖥️ System Log"
- Delete temporary file
- Clean up any orphan files

---

### File 3: `src/backend/frames/__init__.py`

**Changed import order:**
```python
# Import marty.py FIRST since other frames depend on its constants
from backend.frames.marty import (
    CLEANED_MESSAGE_KEY,
    SESSION_PHASE_KEY,
    SPEAKER_KEY,
    MNEMONIC_STATE_KEY,
    MnemonicCoCreatorFrame,
)

from backend.frames.language_checker import LanguageCheckerFrame

from backend.frames.comprehension_tracker import (
    CONCEPT_ASSESSMENTS_KEY,
    ComprehensionLevel,
    ComprehensionTrackerFrame,
    ConceptAssessment,
)

from backend.frames.balanced_turns import (
    BalancedTurnsFrame,
    SUGGESTED_NEXT_SPEAKER_KEY,
    CONSECUTIVE_SAME_SPEAKER_KEY
)
```

**Purpose:** Import `marty.py` first, then `balanced_turns.py` (which no longer imports from marty)

---

### File 4: `src/backend/frames/marty.py`

**Removed imports:**
```python
# REMOVED: from backend.frames.balanced_turns import SUGGESTED_NEXT_SPEAKER_KEY, CONSECUTIVE_SAME_SPEAKER_KEY
```

**Changed shared_context writes:**
```python
# Line 339-340: Use string literals instead of imported constants
'_suggested_next_speaker': None,  # Set by balanced_turns frame later
'_consecutive_same_speaker': 0,   # Set by balanced_turns frame later
```

**Changed shared_context reads:**
```python
# Multiple locations: Use string literals when reading
suggested_next = shared.get('_suggested_next_speaker', '[Next student]')
```

**Purpose:** Break circular dependency by not importing from `balanced_turns.py`

---

### File 5: `src/backend/frames/balanced_turns.py`

**Removed imports:**
```python
# REMOVED: from backend.frames.marty import SPEAKER_KEY, CLEANED_MESSAGE_KEY
```

**Changed shared_context reads:**
```python
# Lines 69-70, 92, 110: Use string literals instead of imported constants
speaker = context['shared_context'].get('_speaker', 'Unknown')
message = context['shared_context'].get('_cleaned_message', '')
previous_speaker = shared.get('_speaker')
```

**Added validation (Line 327-340):**
```python
# Check for multiple questions being asked (count question marks)
question_count = response.count('?')
if question_count > 1:
    return (
        f"TURN-TAKING ERROR: You asked {question_count} questions. "
        f"You should ask ONLY ONE question to {suggested_next}. "
        f"Structure: 1) Acknowledge {previous_speaker} briefly. "
        f"2) Ask ONLY {suggested_next} ONE question to invite them to contribute next."
    )
```

**Purpose:** 
- Break circular dependency by not importing from `marty.py`
- Add question count validation to enforce one-question-per-turn

---

## Results

### ✅ Fixed Issues
1. Terminal log files now contain Python logging output (INFO, WARNING, ERROR)
2. System log integrated into main session markdown (not separate file)
3. No more circular import errors
4. Log messages appear once (not 3x)
5. No orphan `_terminal_log.md` files left behind

### ✅ Session Output
Each session now produces **one markdown file** with structure:
```
# Session Report
...session details...

## 💬 Conversation
...dialogue...

## 🖥️ System Log
```
...all terminal output including Python logging...
```
```

### ✅ Backward Compatibility
- No breaking changes to frame interfaces
- Existing sessions continue to work
- Optional terminal log integration (works if handlers exist, skips if not)

---

## Testing Performed

1. ✅ Started new session → Terminal log captures all output
2. ✅ Python logging (INFO/WARNING) appears in system log
3. ✅ Ended session → Content integrated into main `.md`
4. ✅ No separate `_terminal_log.md` files remain
5. ✅ Each log entry appears once (no duplication)
6. ✅ No circular import errors on startup
7. ✅ Balanced turns validation rejects multiple questions

---

## Files Modified

```
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/scripts/frontend.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frame_engine/core.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frames/__init__.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frames/balanced_turns.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frames/marty.py
```

---

## Notes

- Changes were kept minimal and essential per coding standards
- No new files created (except this documentation)
- Reused existing `TerminalLogger` class instead of creating new abstractions
- Solution integrates cleanly with existing session management flow

