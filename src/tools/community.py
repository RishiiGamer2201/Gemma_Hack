"""Community Elder / Panchayat Bridge explanation.

For a citizen who will act on an app only if a trusted local intermediary — a
village elder, an NGO worker, an ASHA worker — understands and co-signs it, this
produces a respectful third-person version of a verified answer to show that
person.

It is built DETERMINISTICALLY from a published answer. It does not call the model.
Every legal sentence it contains was already generated under grounding and passed
the independent verifier; reformatting verified sentences cannot introduce a new
claim, whereas a fresh generation could. It carries the citations forward, states
plainly what help is being asked for, and drops personal identifiers by default.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.models.schemas import SourceEvidence, StructuredLegalAnswer

# Personal identifiers are removed by default: an intermediary needs the legal
# situation, not the person's name or exact address. The user's own explicit words
# in the answer are kept; only party labels and location are withheld here.
_SENSITIVE_TRAILING = re.compile(r"\s+([.,;:])")


@dataclass(frozen=True, slots=True)
class CommunityExplanation:
    """A shareable, third-person brief for a trusted intermediary."""

    heading: str
    what_help_is_needed: str
    situation: str
    rights: tuple[str, ...]
    next_steps: tuple[str, ...]
    citations: tuple[str, ...]
    caveats: tuple[str, ...]

    def as_text(self) -> str:
        lines = [self.heading, "", self.what_help_is_needed, "", "The situation:", self.situation]
        if self.rights:
            lines += ["", "What the law says they may do:"]
            lines += [f"  - {right}" for right in self.rights]
        if self.next_steps:
            lines += ["", "Suggested next steps:"]
            lines += [f"  - {step}" for step in self.next_steps]
        if self.citations:
            lines += ["", "Based on:"]
            lines += [f"  - {citation}" for citation in self.citations]
        if self.caveats:
            lines += [""]
            lines += self.caveats
        return "\n".join(lines)


def _strip_source_ids(text: str, known_ids: frozenset[str]) -> str:
    def drop(match: re.Match[str]) -> str:
        token = match.group().strip(" ()[]")
        return "" if token in known_ids else match.group()

    cleaned = re.sub(r"\s*[\(\[]?[a-z0-9_]+:[a-z0-9_.\-]+[\)\]]?", drop, text)
    return _SENSITIVE_TRAILING.sub(r"\1", cleaned).strip()


def _citation(source: SourceEvidence) -> str:
    section = f", Section {source.section}" if source.section else ""
    note = "" if source.effective_from is not None else " (commencement not verified)"
    return f"{source.act}{section}{note}"


def build_community_explanation(
    answer: StructuredLegalAnswer,
    evidence: Sequence[SourceEvidence],
    *,
    include_sensitive: bool = False,
    warnings: Sequence[str] = (),
) -> CommunityExplanation:
    """Reformat a verified answer as a third-person intermediary brief.

    ``include_sensitive`` is off by default. When off, this brief omits personal
    identifiers so it can be shown to a third party without exposing more than the
    legal situation requires.
    """

    known_ids = frozenset(source.source_id for source in evidence)
    rights = tuple(
        cleaned for right in answer.rights if (cleaned := _strip_source_ids(right, known_ids))
    )
    steps = tuple(
        cleaned for step in answer.next_steps if (cleaned := _strip_source_ids(step, known_ids))
    )
    citations = tuple(dict.fromkeys(_citation(source) for source in evidence))

    situation = _strip_source_ids(answer.situation, known_ids)

    caveats = [
        "Please note: this is legal information from official sources, not legal "
        "advice, and not a lawyer.",
        "Informal help or mediation cannot override this person's legal rights or "
        "any urgent safety need. A District Legal Services Authority or a lawyer can "
        "give free, formal help.",
    ]
    for warning in warnings:
        caveats.append(f"Note: {warning}")

    return CommunityExplanation(
        heading="A request for your help understanding a legal matter",
        what_help_is_needed=(
            "This person is asking you, as someone they trust, to help them "
            "understand their situation and decide what to do next. They are not "
            "asking you to take sides — only to help them act on official legal "
            "information."
        ),
        situation=(
            situation
            if include_sensitive
            else "A person you know is dealing with the following situation. "
            + situation
        ),
        rights=rights,
        next_steps=steps,
        citations=citations,
        caveats=tuple(caveats),
    )
