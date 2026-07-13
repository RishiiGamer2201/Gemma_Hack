"""Deterministic, offline preprocessing for English, Hindi, and Hinglish text."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from src.models import LegalDomain

from .models import (
    DetectedLanguage,
    IntakeFacts,
    LanguageAssessment,
    TextIntakeResult,
    UrgencyCategory,
    UrgencySignal,
)

MAX_INPUT_CHARACTERS = 20_000

_DANGEROUS_DIRECTIONAL_CONTROLS = frozenset({
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
})

_ROMANIZED_HINDI_MARKERS = frozenset({
    "aaj", "aur", "diya", "hai", "hain", "kal", "kya", "lekin", "mera", "mere",
    "meri", "mila", "mili", "mujhe", "nahi", "nahin", "paisa", "paise", "tha", "thi",
    "unhone",
})

_URGENCY_PHRASES: dict[UrgencyCategory, tuple[str, ...]] = {
    UrgencyCategory.ARREST_OR_DETENTION: (
        "under arrest", "police custody", "being detained", "गिरफ्तार", "हिरासत",
    ),
    UrgencyCategory.VIOLENCE: (
        "threatened to kill", "physical violence", "मारने की धमकी", "हिंसा",
    ),
    UrgencyCategory.IMMEDIATE_EVICTION: (
        "evict me today", "eviction today", "आज घर से निकाल", "अभी घर से निकाल",
    ),
    UrgencyCategory.EXPIRING_DEADLINE: (
        "deadline today", "deadline tomorrow", "last date today", "अंतिम तारीख आज",
    ),
    UrgencyCategory.CHILD_SAFETY: (
        "child is unsafe", "child in danger", "बच्चा खतरे में", "बच्ची खतरे में",
    ),
    UrgencyCategory.SELF_HARM: (
        "harm myself", "kill myself", "thinking about suicide", "attempt suicide",
        "आत्महत्या करना", "खुद को नुकसान",
    ),
    UrgencyCategory.MEDICAL_EMERGENCY: (
        "medical emergency", "needs an ambulance", "चिकित्सा आपातकाल", "एम्बुलेंस चाहिए",
    ),
}


def normalize_intake_text(text: str) -> str:
    """Normalize line endings only; preserve every user token and internal space."""

    if not isinstance(text, str):
        raise TypeError("intake text must be a string")
    if len(text) > MAX_INPUT_CHARACTERS:
        raise ValueError(f"intake text exceeds {MAX_INPUT_CHARACTERS} characters")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("intake text must not be blank")
    for character in normalized:
        category = unicodedata.category(character)
        if (
            (category == "Cc" and character not in {"\n", "\t"})
            or category == "Cs"
            or character in _DANGEROUS_DIRECTIONAL_CONTROLS
        ):
            raise ValueError("intake text contains an unsupported control character")
    return normalized


def detect_language(text: str) -> LanguageAssessment:
    """Classify visible script without translating or guessing the user's identity."""

    normalized = normalize_intake_text(text)
    devanagari = sum(1 for char in normalized if "DEVANAGARI LETTER" in unicodedata.name(char, ""))
    latin = sum(
        1
        for char in normalized
        if "LATIN" in unicodedata.name(char, "") and char.isalpha()
    )
    latin_words = {word.casefold() for word in re.findall(r"[A-Za-z]+", normalized)}
    romanized_hindi_markers = len(latin_words & _ROMANIZED_HINDI_MARKERS)
    if devanagari and latin:
        language = DetectedLanguage.HINGLISH
    elif devanagari:
        language = DetectedLanguage.HINDI
    elif romanized_hindi_markers >= 2:
        language = DetectedLanguage.HINGLISH
    elif latin:
        language = DetectedLanguage.ENGLISH
    else:
        language = DetectedLanguage.UNDETERMINED
    return LanguageAssessment(
        language=language,
        devanagari_letters=devanagari,
        latin_letters=latin,
        romanized_hindi_markers=romanized_hindi_markers,
    )


def detect_urgency_signals(text: str) -> tuple[UrgencySignal, ...]:
    """Return conservative phrase matches that always require confirmation."""

    normalized = normalize_intake_text(text)
    folded = normalized.casefold()
    signals: list[UrgencySignal] = []
    for category, phrases in _URGENCY_PHRASES.items():
        match = next(
            (
                phrase
                for phrase in phrases
                if _contains_actionable_phrase(normalized, folded, phrase)
            ),
            None,
        )
        if match is not None:
            signals.append(UrgencySignal(category=category, matched_phrase=match))
    return tuple(signals)


def _contains_actionable_phrase(original: str, folded: str, phrase: str) -> bool:
    pattern = re.compile(rf"(?<!\w){re.escape(phrase.casefold())}(?!\w)")
    for found in pattern.finditer(folded):
        if _inside_quotation(original, found.start()):
            continue
        prefix = folded[max(0, found.start() - 45):found.start()]
        if re.search(r"(?:\bnot|\bnever|\bno longer|नहीं)\s*$", prefix):
            continue
        if re.search(r"(?:\blast year|\bpreviously|\bformerly|\bused to be)\b[^.!?]*$", prefix):
            continue
        return True
    return False


def _inside_quotation(text: str, position: int) -> bool:
    prefix = text[:position]
    if prefix.count('"') % 2 == 1:
        return True
    return prefix.rfind("“") > prefix.rfind("”")


def build_restatement(facts: IntakeFacts, language: DetectedLanguage) -> str:
    """Restate only explicit fields, without adding law, deadlines, or conclusions."""

    details: list[str] = [facts.incident_summary]
    if facts.incident_date is not None:
        details.append(f"Date: {facts.incident_date.isoformat()}")
    if facts.location is not None:
        details.append(f"Location: {facts.location}")
    if facts.parties:
        details.append(f"People or parties: {', '.join(facts.parties)}")
    if facts.documents:
        details.append(f"Documents mentioned: {', '.join(facts.documents)}")
    if facts.missing_material_facts:
        details.append(f"Still to confirm: {', '.join(facts.missing_material_facts)}")
    prefix = (
        "मैंने यह समझा: "
        if language is DetectedLanguage.HINDI
        else "Here is what I understood: "
    )
    return prefix + " ".join(details) + " Please confirm or correct these details."


def process_text_intake(
    text: str,
    *,
    incident_summary: str | None = None,
    incident_date: date | None = None,
    jurisdiction: str | None = None,
    location: str | None = None,
    domain: LegalDomain = LegalDomain.OTHER,
    parties: tuple[str, ...] = (),
    material_facts: tuple[str, ...] = (),
    documents: tuple[str, ...] = (),
    missing_material_facts: tuple[str, ...] = (),
) -> TextIntakeResult:
    """Assemble explicit intake fields; the narrative is never semantically inferred."""

    normalized = normalize_intake_text(text)
    language = detect_language(normalized)
    facts = IntakeFacts(
        incident_summary=incident_summary if incident_summary is not None else normalized,
        incident_date=incident_date,
        jurisdiction=jurisdiction,
        location=location,
        domain=domain,
        parties=parties,
        material_facts=material_facts,
        documents=documents,
        missing_material_facts=missing_material_facts,
    )
    return TextIntakeResult(
        normalized_text=normalized,
        language=language,
        facts=facts,
        urgency_signals=detect_urgency_signals(normalized),
        restatement=build_restatement(facts, language.language),
    )
