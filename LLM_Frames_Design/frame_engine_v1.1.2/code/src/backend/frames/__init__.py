"""Reusable Frame implementations for the Rodin Frame Engine.

This package exports frame implementations and their associated data models
(shared context keys, enums, TypedDicts).
"""
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
from backend.frames.phases_checker import PhasesCheckerFrame, PHASE_GOALS

__all__ = [
    # Frames
    'LanguageCheckerFrame',
    'BalancedTurnsFrame',
    'ComprehensionTrackerFrame',
    'MnemonicCoCreatorFrame',
    'PhasesCheckerFrame',

    # --- Data Models & Shared Keys ---

    # From balanced_turns.py
    'SUGGESTED_NEXT_SPEAKER_KEY',
    'CONSECUTIVE_SAME_SPEAKER_KEY',

    # From comprehension_tracker.py
    'CONCEPT_ASSESSMENTS_KEY',
    'ComprehensionLevel',
    'ConceptAssessment',

    # From marty.py
    'CLEANED_MESSAGE_KEY',
    'SESSION_PHASE_KEY',
    'SPEAKER_KEY',
    'MNEMONIC_STATE_KEY',

    # From phases_checker.py
    'PHASE_GOALS',
]

