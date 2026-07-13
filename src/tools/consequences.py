"""What happens if I do nothing.

Built deterministically from verified deadline records. No model call: the whole
risk of this feature is a made-up number, and a generation step is exactly where
one would come from.

Rules it keeps:

* Every date is computed from a period quoted out of official text.
* A statutory consequence and a practical risk are labelled differently and never
  blended, because "the commission shall not admit it" and "evidence gets harder to
  find" are not the same kind of statement.
* When the clock's start date is unknown, no date is computed and the app asks for
  it instead of guessing.
* When there are no records for the situation, the answer is that the sources are
  silent. It never invents a deadline to make the feature look useful.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from src.legal_time.deadlines import DeadlineRecord
from src.models.schemas import LegalDomain, SourceEvidence
from src.retrieval.types import RetrievalDocument


@dataclass(frozen=True, slots=True)
class Consequence:
    deadline_id: str
    title: str
    runs_from: str
    period: str
    due_on: date | None
    days_remaining: int | None
    expired: bool
    consequence: str
    consequence_kind: str
    depends_on: tuple[str, ...]
    citation: str
    source_id: str
    official_url: str | None
    quote: str
    unverified_commencement: bool
    review_status: str


@dataclass(frozen=True, slots=True)
class ConsequenceReport:
    consequences: tuple[Consequence, ...]
    questions: tuple[str, ...]
    notes: tuple[str, ...]

    @property
    def sources_are_silent(self) -> bool:
        return not self.consequences


def build_consequences(
    records: Sequence[DeadlineRecord],
    domain: LegalDomain,
    evidence: Sequence[SourceEvidence],
    *,
    start_date: date | None,
    today: date | None = None,
    documents: Sequence[RetrievalDocument] = (),
) -> ConsequenceReport:
    """Explain the cost of inaction, using only verified deadline records.

    ``documents`` resolves a citation for a deadline whose chunk was not in the
    retrieved bundle. A user must see "Code on Wages, Section 45", not a corpus
    identifier, and the deadline is cited whether or not retrieval happened to
    surface that particular section.
    """

    now = today or date.today()
    by_source = {item.source_id: item for item in evidence}
    by_chunk = {document.source_id: document.metadata for document in documents}
    relevant = [record for record in records if record.domain is domain]

    if not relevant:
        return ConsequenceReport(
            consequences=(),
            questions=(),
            notes=(
                "The official sources reviewed for this kind of dispute do not state "
                "a deadline that applies here. That does not mean there is none — it "
                "means this tool will not guess one. A legal-aid lawyer can tell you.",
            ),
        )

    questions: list[str] = []
    notes: list[str] = []
    if start_date is None:
        # Without the start date there is no clock. Ask; do not assume today.
        questions.append(
            "When did this happen? Each time limit below runs from a specific date, "
            "and without it the deadline cannot be worked out."
        )

    consequences: list[Consequence] = []
    for record in relevant:
        source = by_source.get(record.source_id)
        metadata = by_chunk.get(record.source_id, {})
        due = record.period.add_to(start_date) if start_date is not None else None
        remaining = (due - now).days if due is not None else None

        act = source.act if source else metadata.get("act")
        section = source.section if source else metadata.get("section")
        citation = f"{act}, Section {section}" if act and section else record.source_id
        url = (
            str(source.official_url)
            if source
            else (str(metadata["official_url"]) if metadata.get("official_url") else None)
        )
        undated = (
            source.effective_from is None
            if source
            else metadata.get("effective_from") in (None, "")
        )
        consequences.append(
            Consequence(
                deadline_id=record.deadline_id,
                title=record.title,
                runs_from=record.runs_from,
                period=f"{record.period.count} {record.period.unit}"
                + ("s" if record.period.count != 1 else ""),
                due_on=due,
                days_remaining=remaining,
                expired=bool(due is not None and due < now),
                consequence=record.consequence,
                consequence_kind=record.consequence_kind,
                depends_on=record.depends_on,
                citation=citation,
                source_id=record.source_id,
                official_url=url,
                quote=record.quote,
                unverified_commencement=bool(undated),
                review_status=record.review_status,
            )
        )

    if any(item.unverified_commencement for item in consequences):
        notes.append(
            "The commencement of at least one Act below is not proven by its own "
            "text, so it is not confirmed to have been in force on your date. Treat "
            "the time limit as indicative until a lawyer confirms it."
        )
    if any(item.review_status != "reviewed" for item in consequences):
        notes.append(
            "These time limits are quoted from the official text but have not yet "
            "been signed off by a human legal reviewer. Check with a legal-aid "
            "lawyer before relying on a date."
        )
    if any(item.expired for item in consequences):
        notes.append(
            "A time limit below appears to have passed. That is not the end of the "
            "matter — the law usually allows a late claim if you can show a good "
            "reason for the delay — but you should get help quickly."
        )
    notes.append(
        "This lists what the cited sources say. It is not a prediction of what will "
        "happen in your case."
    )
    return ConsequenceReport(
        consequences=tuple(consequences),
        questions=tuple(questions),
        notes=tuple(notes),
    )
