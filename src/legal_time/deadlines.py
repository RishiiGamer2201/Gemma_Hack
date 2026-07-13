"""Deadline records that can only exist if the official text says so.

"What happens if I do nothing" is the feature most likely to invent a number. A
made-up limitation period is worse than silence: a citizen who believes they have
two years when they have thirty days loses the claim entirely.

So a deadline here is not a fact someone typed. It is a quote. Every record must
carry the exact wording from an official chunk, and ``load_deadlines`` refuses any
record whose quote does not appear verbatim in the chunk it cites. A deadline that
cannot be found in the law does not load, and a feature with no records says the
sources are silent rather than filling the gap.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from src.models.schemas import LegalDomain, NonEmptyText, ShortText, StrictModel
from src.retrieval.types import RetrievalDocument


class DeadlineError(RuntimeError):
    """A bounded failure loading deadline records. Never a silent skip."""


class DeadlineUnit(StrictModel):
    """A period expressed the way the statute expresses it."""

    count: Annotated[int, Field(ge=1, le=100)]
    unit: Literal["day", "month", "year"]

    def add_to(self, start: date) -> date:
        if self.unit == "day":
            return start + timedelta(days=self.count)
        months = self.count if self.unit == "month" else self.count * 12
        year = start.year + (start.month - 1 + months) // 12
        month = (start.month - 1 + months) % 12 + 1
        # Clamp: 31 January + 1 month is the end of February, not an invalid date.
        day = min(start.day, _days_in_month(year, month))
        return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day


class DeadlineRecord(StrictModel):
    """One deadline, quoted from official text.

    ``quote`` must appear verbatim in the chunk named by ``source_id``. That is the
    whole safety property: a record is not a claim about the law, it is a pointer
    into it.
    """

    deadline_id: Annotated[str, Field(pattern=r"^[a-z0-9_.-]+$", max_length=80)]
    domain: LegalDomain
    title: ShortText
    # What starts the clock, in the statute's own terms.
    runs_from: ShortText
    period: DeadlineUnit
    consequence: NonEmptyText
    # Statutory consequence, or practical risk? They are not the same thing and must
    # not be presented as if they were.
    consequence_kind: Literal["statutory", "practical"]
    depends_on: tuple[ShortText, ...] = ()
    source_id: Annotated[str, Field(min_length=1, max_length=200)]
    quote: NonEmptyText
    review_status: Literal["pending_human_review", "reviewed"] = "pending_human_review"

    @model_validator(mode="after")
    def practical_risk_must_not_masquerade_as_law(self) -> DeadlineRecord:
        if self.consequence_kind == "practical" and not self.depends_on:
            raise ValueError(
                "a practical risk must say what it depends on; only a statutory "
                "consequence may be stated flatly"
            )
        return self


def _normalise(text: str) -> str:
    """Whitespace-insensitive comparison. PDF extraction inserts odd breaks."""

    return re.sub(r"\s+", " ", text).strip().casefold()


def load_deadlines(
    path: str | Path,
    documents: Sequence[RetrievalDocument],
) -> tuple[DeadlineRecord, ...]:
    """Load deadline records, verifying every quote against the cited chunk.

    A record whose quote is not in its chunk is a fabricated deadline. It raises
    rather than being skipped: a silently dropped deadline is a feature that quietly
    stops warning people.
    """

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeadlineError(f"could not read the deadline records: {source}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("deadlines"), list):
        raise DeadlineError("deadline file must be an object with a 'deadlines' array")

    try:
        records = tuple(
            DeadlineRecord.model_validate(item) for item in payload["deadlines"]
        )
    except ValidationError as exc:
        raise DeadlineError(f"a deadline record failed schema validation: {exc}") from exc

    ids = [record.deadline_id for record in records]
    if len(ids) != len(set(ids)):
        raise DeadlineError("deadline_id values must be unique")

    by_id = {document.source_id: document for document in documents}
    for record in records:
        document = by_id.get(record.source_id)
        if document is None:
            raise DeadlineError(
                f"{record.deadline_id} cites {record.source_id}, which is not in the corpus"
            )
        body = str(document.metadata.get("source_text", ""))
        if _normalise(record.quote) not in _normalise(body):
            raise DeadlineError(
                f"{record.deadline_id} quotes text that does not appear in "
                f"{record.source_id}. A deadline that is not in the law does not load."
            )
    return records


def deadlines_for(
    records: Sequence[DeadlineRecord],
    domain: LegalDomain,
    *,
    approved_only: bool = False,
) -> tuple[DeadlineRecord, ...]:
    return tuple(
        record
        for record in records
        if record.domain is domain
        and (not approved_only or record.review_status == "reviewed")
    )
