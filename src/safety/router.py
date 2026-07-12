"""Offline routing that runs after fact confirmation and before retrieval."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from src.intake import MAX_INPUT_CHARACTERS, UrgencyCategory, normalize_intake_text
from src.models import ConfirmedFacts, LegalDomain, WorkflowStage
from src.workflow import LegalWorkflow, WorkflowError, WorkflowSnapshot

from .models import (
    DocumentSafetyWarning,
    MissingFactQuestion,
    PowerRelationship,
    RoleSignal,
    RoutePriority,
    SafetyRouteDecision,
)


MAX_UNTRUSTED_DOCUMENTS = 5
MAX_DOCUMENT_CHARACTERS = MAX_INPUT_CHARACTERS

_DATE_MATERIAL_DOMAINS = {
    LegalDomain.CRIMINAL,
    LegalDomain.LABOUR,
    LegalDomain.CONSUMER,
    LegalDomain.TENANCY_PROPERTY,
}

_ROLE_TERMS: dict[PowerRelationship, tuple[tuple[str, ...], tuple[str, ...]]] = {
    PowerRelationship.POLICE_CITIZEN: (
        ("police", "police officer", "पुलिस", "थाना"),
        ("citizen", "complainant", "accused", "नागरिक", "शिकायतकर्ता", "आरोपी"),
    ),
    PowerRelationship.EMPLOYER_WORKER: (
        ("employer", "manager", "boss", "company", "नियोक्ता"),
        ("worker", "employee", "wages", "salary", "कर्मचारी", "वेतन"),
    ),
    PowerRelationship.LANDLORD_TENANT: (
        ("landlord", "मकान मालिक"),
        ("tenant", "rent", "security deposit", "किरायेदार", "किराया"),
    ),
    PowerRelationship.ABUSER_SURVIVOR: (
        ("abuser", "harasser", "threatening partner", "हमलावर"),
        ("survivor", "victim", "person facing abuse", "पीड़ित"),
    ),
}

_PROTECTIVE_PROMPTS = {
    PowerRelationship.POLICE_CITIZEN: (
        "If you feel pressured, seek a lawyer or legal-aid worker before signing "
        "or sharing originals.",
    ),
    PowerRelationship.EMPLOYER_WORKER: (
        "Preserve wage, attendance, bank, and communication records; share copies where possible.",
    ),
    PowerRelationship.LANDLORD_TENANT: (
        "Preserve the agreement, payment records, condition photos, and written communications.",
    ),
    PowerRelationship.ABUSER_SURVIVOR: (
        "Prioritize immediate physical safety and contact trusted or emergency "
        "human help if needed.",
    ),
}

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(
            r"\b(?:ignore|disregard) (?:all |the )?(?:prior|previous|system) instructions?\b",
            re.I,
        ),
    ),
    ("system_prompt", re.compile(r"\b(?:reveal|print|show) (?:the )?system prompt\b", re.I)),
    (
        "role_override",
        re.compile(r"\byou are now\b|\bact as (?:an?|the)\b|\bbecome (?:an?|the)\b", re.I),
    ),
    ("tool_command", re.compile(r"\b(?:call|run|execute) (?:the )?(?:tool|command|shell)\b", re.I)),
)

_DISALLOWED_REQUESTS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:what(?:'s| is)|estimate|assess|rate|calculate|predict|give|tell)\b"
        r".{0,50}\b(?:win probability|chance of winning|odds of winning)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:predict|estimate|tell me|what(?:'s| is)|how (?:many|long))\b"
        r".{0,50}\b(?:sentence|punishment|years? (?:in )?(?:jail|prison))\b",
        re.I,
    ),
    re.compile(r"\bguarantee (?:that )?(?:i|we) (?:will )?win\b", re.I),
    re.compile(
        r"\b(?:what(?:'s| is| are)|estimate|assess|calculate|predict|give|tell)\b"
        r".{0,50}\b(?:probability|chance|odds|likelihood) (?:of )?(?:success|succeeding)\b",
        re.I,
    ),
    re.compile(r"\bwill (?:i|we) (?:win|succeed)\b", re.I),
)


def route_confirmed_case(
    facts: ConfirmedFacts,
    *,
    confirmed_urgencies: Iterable[UrgencyCategory] = (),
    untrusted_document_texts: Iterable[str] = (),
    requested_output: str | None = None,
) -> SafetyRouteDecision:
    """Create a route from confirmed facts; untrusted documents cannot affect it."""

    if not facts.confirmed or facts.confirmed_at is None:
        raise ValueError("safety routing requires explicitly confirmed facts")
    urgencies = tuple(confirmed_urgencies)
    if any(not isinstance(item, UrgencyCategory) for item in urgencies):
        raise TypeError("confirmed urgencies must use UrgencyCategory values")
    if len(urgencies) != len(set(urgencies)):
        raise ValueError("confirmed urgency categories must be unique")
    document_warnings = inspect_untrusted_documents(untrusted_document_texts)
    facts_fingerprint = fingerprint_confirmed_facts(facts)
    role_signals = detect_role_signals(facts)
    protective_prompts = tuple(
        prompt
        for signal in role_signals
        for prompt in _PROTECTIVE_PROMPTS[signal.relationship]
    )

    if urgencies:
        return SafetyRouteDecision(
            facts_fingerprint=facts_fingerprint,
            priority=RoutePriority.IMMEDIATE_HUMAN_HELP,
            domain=facts.domain,
            jurisdiction=facts.jurisdiction,
            incident_date=facts.incident_date,
            confirmed_urgencies=urgencies,
            role_signals=role_signals,
            protective_prompts=(
                "Address immediate safety and human help before general legal information.",
                *protective_prompts,
            ),
            document_warnings=document_warnings,
            general_explanation_allowed=False,
            human_help_required=True,
            terminal_reason="Confirmed urgency requires immediate safety or human-help routing.",
        )

    clean_request = (
        normalize_intake_text(requested_output)
        if requested_output is not None
        else None
    )
    if clean_request and _requests_disallowed_output(clean_request):
        return SafetyRouteDecision(
            facts_fingerprint=facts_fingerprint,
            priority=RoutePriority.HARD_ABSTAIN,
            domain=facts.domain,
            jurisdiction=facts.jurisdiction,
            incident_date=facts.incident_date,
            role_signals=role_signals,
            protective_prompts=protective_prompts,
            document_warnings=document_warnings,
            general_explanation_allowed=False,
            human_help_required=False,
            terminal_reason=(
                "Outcome probabilities, guarantees, and sentence predictions are unsupported."
            ),
        )

    missing_questions = build_missing_questions(facts)
    if missing_questions:
        return SafetyRouteDecision(
            facts_fingerprint=facts_fingerprint,
            priority=RoutePriority.NEEDS_INFORMATION,
            domain=facts.domain,
            jurisdiction=facts.jurisdiction,
            incident_date=facts.incident_date,
            role_signals=role_signals,
            protective_prompts=protective_prompts,
            missing_questions=missing_questions,
            document_warnings=document_warnings,
            general_explanation_allowed=False,
            human_help_required=False,
        )

    return SafetyRouteDecision(
        facts_fingerprint=facts_fingerprint,
        priority=RoutePriority.STANDARD,
        domain=facts.domain,
        jurisdiction=facts.jurisdiction,
        incident_date=facts.incident_date,
        role_signals=role_signals,
        protective_prompts=protective_prompts,
        document_warnings=document_warnings,
        general_explanation_allowed=True,
        human_help_required=False,
    )


def build_missing_questions(facts: ConfirmedFacts) -> tuple[MissingFactQuestion, ...]:
    questions: list[MissingFactQuestion] = []
    if facts.jurisdiction is None:
        questions.append(MissingFactQuestion(
            fact_key="jurisdiction",
            question="In which state or territory did this happen?",
            reason="Applicable authorities and rules can depend on jurisdiction.",
        ))
    if facts.domain is LegalDomain.OTHER:
        questions.append(MissingFactQuestion(
            fact_key="legal_domain",
            question=(
                "What type of dispute is this: criminal, work, consumer, tenancy, "
                "or constitutional?"
            ),
            reason="The retrieval collection cannot be selected safely without the dispute type.",
        ))
    if facts.domain in _DATE_MATERIAL_DOMAINS and facts.incident_date is None:
        questions.append(MissingFactQuestion(
            fact_key="incident_date",
            question="What is the incident or notice date?",
            reason="The applicable law or procedure may depend on the date.",
        ))
    return tuple(questions)


def detect_role_signals(facts: ConfirmedFacts) -> tuple[RoleSignal, ...]:
    text = " ".join((facts.incident_summary, *facts.parties, *facts.material_facts)).casefold()
    signals: list[RoleSignal] = []
    for relationship, (authority_terms, citizen_terms) in _ROLE_TERMS.items():
        left = next((term for term in authority_terms if _contains_term(text, term)), None)
        right = next((term for term in citizen_terms if _contains_term(text, term)), None)
        if left is not None and right is not None:
            signals.append(RoleSignal(relationship=relationship, matched_role_terms=(left, right)))
    return tuple(signals)


def inspect_untrusted_documents(texts: Iterable[str]) -> tuple[DocumentSafetyWarning, ...]:
    records = tuple(texts)
    if len(records) > MAX_UNTRUSTED_DOCUMENTS:
        raise ValueError(f"at most {MAX_UNTRUSTED_DOCUMENTS} untrusted documents are allowed")
    found: list[DocumentSafetyWarning] = []
    seen: set[str] = set()
    for text in records:
        normalized = normalize_intake_text(text)
        if len(normalized) > MAX_DOCUMENT_CHARACTERS:
            raise ValueError(f"untrusted document exceeds {MAX_DOCUMENT_CHARACTERS} characters")
        for pattern_name, pattern in _INJECTION_PATTERNS:
            if pattern.search(normalized) and pattern_name not in seen:
                found.append(DocumentSafetyWarning(pattern_name=pattern_name))
                seen.add(pattern_name)
    return tuple(found)


def apply_route_decision(
    workflow: LegalWorkflow,
    decision: SafetyRouteDecision,
) -> WorkflowSnapshot:
    """Advance only safe terminal/ready routes; missing information stays blocked."""

    if workflow.snapshot.stage is not WorkflowStage.CONFIRMED:
        raise WorkflowError("Safety decisions can be applied only after fact confirmation.")
    facts = workflow.snapshot.facts
    if facts is None or decision.facts_fingerprint != fingerprint_confirmed_facts(facts):
        raise WorkflowError("Safety decision does not belong to this workflow's confirmed facts.")
    if decision.priority is RoutePriority.IMMEDIATE_HUMAN_HELP:
        return workflow.complete_safety_routing(immediate_human_help_required=True)
    if decision.priority is RoutePriority.STANDARD:
        return workflow.complete_safety_routing(immediate_human_help_required=False)
    if decision.priority is RoutePriority.HARD_ABSTAIN:
        return workflow.abstain(decision.terminal_reason or "The requested output is unsupported.")
    return workflow.snapshot


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", text) is not None


def _requests_disallowed_output(text: str) -> bool:
    for pattern in _DISALLOWED_REQUESTS:
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 30):match.start()]
            if re.search(r"\b(?:do not|don't|avoid|without)\s*$", prefix, re.I):
                continue
            if re.search(
                r"\b(?:why|explain why)\b.{0,25}\b(?:cannot|can't|won't|shouldn't|must not)\b",
                match.group(),
                re.I,
            ):
                continue
            return True
    return False


def fingerprint_confirmed_facts(facts: ConfirmedFacts) -> str:
    """Bind a route decision to the exact confirmed record it evaluated."""

    canonical = json.dumps(
        facts.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
