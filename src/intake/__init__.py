"""Offline intake preprocessing and confirmation-ready contracts."""

from .models import (
    DetectedLanguage,
    IntakeFacts,
    LanguageAssessment,
    TextIntakeResult,
    UrgencyCategory,
    UrgencySignal,
)
from .text import (
    MAX_INPUT_CHARACTERS,
    build_restatement,
    detect_language,
    detect_urgency_signals,
    normalize_intake_text,
    process_text_intake,
)

__all__ = [
    "DetectedLanguage",
    "IntakeFacts",
    "LanguageAssessment",
    "MAX_INPUT_CHARACTERS",
    "TextIntakeResult",
    "UrgencyCategory",
    "UrgencySignal",
    "build_restatement",
    "detect_language",
    "detect_urgency_signals",
    "normalize_intake_text",
    "process_text_intake",
]
