"""Date-aware IPC/BNS conversion.

On 1 July 2024 the IPC was replaced by the BNS. Which code governs a case depends
on when the incident happened, not on when the person asks. That is the whole
feature, and it is also the whole risk: section numbers did not carry across, so
"IPC 420 became BNS 420" is a guess, and "IPC 420 became BNS 318" is a claim that
needs a human to have checked it.

Three things this refuses to do:

* It never infers a mapping from section numbers. A mapping exists only if a human
  reviewer approved it. Otherwise the answer is "no approved mapping", not a guess.
* It never presents BNS text as governing a pre-BNS incident.
* It never pretends to quote the IPC. The IPC is NOT in this build's corpus, so for
  an incident before 1 July 2024 there is no text here to ground an answer in, and
  it says so instead of substituting the BNS.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from src.retrieval.types import RetrievalDocument

from .mapping import BNS_EFFECTIVE_DATE, LegalMapping, MappingCatalog

_EXPLICIT = re.compile(r"\b(ipc|bns)\s*(?:section\s*)?(\d+[a-z]?)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """What the app may show for an IPC/BNS question."""

    query: str
    incident_date: date | None
    # Which code governs, once the date is known.
    governing_code: str | None
    mappings: tuple[LegalMapping, ...] = ()
    grounded_bns_sections: tuple[str, ...] = ()
    questions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_approved_mapping(self) -> bool:
        return bool(self.mappings)


def _referenced_sections(query: str) -> set[tuple[str, str]]:
    return {
        (match.group(1).casefold(), match.group(2).casefold())
        for match in _EXPLICIT.finditer(query)
    }


def convert(
    query: str,
    *,
    incident_date: date | None,
    catalog: MappingCatalog,
    documents: Sequence[RetrievalDocument] = (),
) -> ConversionResult:
    """Route an IPC/BNS question by incident date, using approved mappings only."""

    clean = query.strip()
    if not clean:
        raise ValueError("a conversion query cannot be blank")

    questions: list[str] = []
    warnings: list[str] = []

    if incident_date is None:
        # Without the date there is no answer, only two possibilities. Ask.
        questions.append(
            "Did this happen before or after 1 July 2024? On that date the Indian "
            "Penal Code was replaced by the Bharatiya Nyaya Sanhita, and which one "
            "applies to your case depends entirely on the date."
        )
        governing = None
    elif incident_date >= BNS_EFFECTIVE_DATE:
        governing = "BNS"
    else:
        governing = "IPC"
        warnings.append(
            "This incident happened before 1 July 2024, so the Indian Penal Code "
            "governs it, not the Bharatiya Nyaya Sanhita. The IPC is NOT included in "
            "this build's official corpus, so nothing here can be quoted as the law "
            "for your case. Anything shown below about the BNS is for orientation "
            "only and does not apply to you. Please speak to a legal-aid lawyer."
        )

    lookup = catalog.lookup(clean, incident_date=incident_date)
    mappings = lookup.candidates

    if not mappings:
        referenced = _referenced_sections(clean)
        if referenced:
            warnings.append(
                "There is no human-approved IPC/BNS mapping for this provision in "
                "this build. Do not assume the number carried across: when the codes "
                "changed, provisions were split, merged, reworded, and dropped, so a "
                "matching number is not a matching offence. Check the official codes "
                "or ask a lawyer."
            )
        else:
            warnings.append(
                "No approved IPC/BNS mapping matched this question. A mapping is "
                "never inferred from a section number."
            )

    # Where a mapping IS approved, confirm its BNS targets actually exist in the
    # corpus, so the app cannot cite a section it has no text for.
    grounded: list[str] = []
    if mappings and governing == "BNS":
        available = {
            str(document.metadata.get("section"))
            for document in documents
            if str(document.metadata.get("corpus_source_id", "")).startswith("bns_2023")
        }
        for mapping in mappings:
            for provision in mapping.target_provisions:
                if provision.section in available:
                    grounded.append(provision.section)
                else:
                    warnings.append(
                        f"An approved mapping points to BNS section {provision.section}, "
                        "but that section's text is not in this build's corpus, so it "
                        "cannot be quoted here."
                    )

    return ConversionResult(
        query=clean,
        incident_date=incident_date,
        governing_code=governing,
        mappings=mappings,
        grounded_bns_sections=tuple(dict.fromkeys(grounded)),
        questions=tuple(questions),
        warnings=tuple(warnings),
    )
