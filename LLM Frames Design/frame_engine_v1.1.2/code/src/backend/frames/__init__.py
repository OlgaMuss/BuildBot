"""Reusable Frame implementations for the Rodin Frame Engine.

This package exports frame implementations and their associated data models
(shared context keys, enums, TypedDicts).
"""
from backend.frames.language_checker import LanguageCheckerFrame
from backend.frames.balanced_turns import BalancedTurnsFrame
from backend.frames.comprehension_tracker import (
    CONCEPT_ASSESSMENTS_KEY,
    ComprehensionLevel,
    ComprehensionTrackerFrame,
    ConceptAssessment,
)
from backend.frames.marty import (
    CLEANED_MESSAGE_KEY,
    CONSECUTIVE_SAME_SPEAKER_KEY,
    SESSION_PHASE_KEY,
    SPEAKER_KEY,
    SUGGESTED_NEXT_SPEAKER_KEY,
    MnemonicCoCreatorFrame,
)
from backend.frames.phases_checker import PhasesCheckerFrame, PHASE_GOALS

__all__ = [
    # Frames
    'LanguageCheckerFrame',
    'BalancedTurnsFrame',
    'ComprehensionTrackerFrame',
    'MnemonicCoCreatorFrame',
    'PhasesCheckerFrame',
    # Comprehension Tracker data models
    'CONCEPT_ASSESSMENTS_KEY',
    'ComprehensionLevel',
    'ConceptAssessment',
    # Marty shared context keys
    'CLEANED_MESSAGE_KEY',
    'CONSECUTIVE_SAME_SPEAKER_KEY',
    'SESSION_PHASE_KEY',
    'SPEAKER_KEY',
    'SUGGESTED_NEXT_SPEAKER_KEY',
    # Phase Goals
    'PHASE_GOALS',
]

