# Changes Documentation: Terminal Log Integration & Circular Import Fix

**Date:** 2025-12-08  
**Version:** frame_engine_v1.1.2  

---

## Summary

Fixed terminal logging to capture Python logging output and integrate it into session markdown reports. Fixed circular import between `marty.py` and `balanced_turns.py`.

---

## Changes Made

### 1. Terminal Logging Integration

**Problem:** Terminal log files were empty because Python's `logging` module output wasn't being captured.

**Files Modified:**
- `scripts/frontend.py` (lines 136-166)
- `src/backend/frame_engine/core.py` (lines 562-602)

**Solution:**

#### `frontend.py` - Capture Python Logging
```python
# Add FileHandler to capture logging module output
log_handler = logging.FileHandler(terminal_log_path, mode='a')
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(log_handler)
```

**Prevents duplicate logging:**
```python
# Remove old FileHandlers before adding new one
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.FileHandler):
        handler.close()
        root_logger.removeHandler(handler)
```

**Cleanup orphan files:**
```python
# Delete leftover terminal logs from incomplete sessions
for old_log in sessions_dir.glob('*_terminal_log.md'):
    old_log.unlink()
```

#### `core.py` - Integrate Log Into Markdown
```python
# Read terminal log and append to markdown report
terminal_log_path = self.output_dir / f"session_{self.session_id}_terminal_log.md"
if terminal_log_path.exists():
    terminal_content = terminal_log_path.read_text(encoding='utf-8')
    if terminal_content.strip():
        f.write("## 🖥️ System Log\n\n```\n")
        f.write(terminal_content)
        f.write("```\n\n")
    terminal_log_path.unlink()  # Delete temp file
```

**Result:**
- ✅ One `.md` file per session (not two)
- ✅ System log integrated at end of markdown report
- ✅ No duplicate log messages
- ✅ No orphan `_terminal_log.md` files

---

### 2. Circular Import Fix

**Problem:** `ImportError: cannot import name 'SPEAKER_KEY' from partially initialized module 'backend.frames.marty'` due to circular dependency between `marty.py` ↔ `balanced_turns.py`.

**Files Modified:**
- `src/backend/frames/__init__.py`
- `src/backend/frames/marty.py` 
- `src/backend/frames/balanced_turns.py`

**Solution:** Each frame defines its own constants and uses string literals when reading from `shared_context`.

#### `marty.py`
- Removed import of `SUGGESTED_NEXT_SPEAKER_KEY`, `CONSECUTIVE_SAME_SPEAKER_KEY`
- Uses string literals: `'_suggested_next_speaker'`, `'_consecutive_same_speaker'` when reading
- Defines: `SPEAKER_KEY`, `CLEANED_MESSAGE_KEY`, etc. when writing

#### `balanced_turns.py`
- Removed import of `SPEAKER_KEY`, `CLEANED_MESSAGE_KEY`
- Uses string literals: `'_speaker'`, `'_cleaned_message'` when reading
- Defines: `SUGGESTED_NEXT_SPEAKER_KEY = '_suggested_next_speaker'` when writing

#### `__init__.py`
- Import `marty.py` FIRST (before other frames)
- Then import `balanced_turns.py` (no longer imports from marty)

**Result:**
- ✅ No circular imports
- ✅ Both frames read/write same keys in `shared_context`
- ✅ Minimal changes (no new files created)

---

### 3. Balanced Turns Enhancement

**File Modified:** `src/backend/frames/balanced_turns.py` (lines 324-340)

**Added:** Question count validation to enforce one-question-per-turn rule.

```python
question_count = response.count('?')
if question_count > 1:
    return (
        f"TURN-TAKING ERROR: You asked {question_count} questions. "
        f"You should ask ONLY ONE question to {suggested_next}..."
    )
```

**Result:** Marty's responses are rejected if they contain multiple questions.

---

## Files Changed

```
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/scripts/frontend.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frame_engine/core.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frames/__init__.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frames/balanced_turns.py
modified:   LLM_Frames_Design/frame_engine_v1.1.2/code/src/backend/frames/marty.py
```

---

## Testing

1. ✅ Start new session → Terminal log captures Python logging
2. ✅ End session → Log integrated into main `.md` file
3. ✅ No separate `_terminal_log.md` files remain
4. ✅ Each log message appears once (not 3x)
5. ✅ No circular import errors
6. ✅ Balanced turns validation works correctly

---

## Backward Compatibility

- ✅ No breaking changes
- ✅ Existing sessions work unchanged
- ✅ All frame interfaces preserved
