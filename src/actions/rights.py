"""Rights checklists that can only say what the official text says.

The existing evidence checklists are preparation guidance and deliberately carry no
legal claim. A *rights* checklist is different: telling someone "the police must
tell you why you are being arrested" IS a legal claim, and an invented one is the
kind of error that gets a person hurt.

So a right here is a quote, exactly like a deadline. Every entry carries the wording
from an official chunk, and ``load_rights`` refuses any entry whose quote does not
appear verbatim in the chunk it cites. A right that is not in the law does not load.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError

from src.models.schemas import LegalDomain, NonEmptyText, ShortText, StrictModel
from src.retrieval.types import RetrievalDocument


class RightsError(RuntimeError):
    """A bounded failure loading rights entries. Never a silent skip."""


class RightEntry(StrictModel):
    """One right, quoted from official text.

    ``statement`` is the plain-language version a citizen reads. ``quote`` is the
    official wording it rests on, and it must be findable in ``source_id``. The
    statement may simplify; it may not add.
    """

    right_id: Annotated[str, Field(pattern=r"^[a-z0-9_.-]+$", max_length=80)]
    domain: LegalDomain
    statement: NonEmptyText
    # What the person can actually do about it. Not a legal strategy, a next step.
    what_you_can_do: ShortText | None = None
    source_id: Annotated[str, Field(min_length=1, max_length=200)]
    quote: NonEmptyText
    review_status: Literal["pending_human_review", "reviewed"] = "pending_human_review"


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def load_rights(
    path: str | Path,
    documents: Sequence[RetrievalDocument],
) -> tuple[RightEntry, ...]:
    """Load rights entries, verifying every quote against the chunk it cites."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RightsError(f"could not read the rights entries: {source}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("rights"), list):
        raise RightsError("rights file must be an object with a 'rights' array")

    try:
        entries = tuple(RightEntry.model_validate(item) for item in payload["rights"])
    except ValidationError as exc:
        raise RightsError(f"a rights entry failed schema validation: {exc}") from exc

    ids = [entry.right_id for entry in entries]
    if len(ids) != len(set(ids)):
        raise RightsError("right_id values must be unique")

    by_id = {document.source_id: document for document in documents}
    for entry in entries:
        document = by_id.get(entry.source_id)
        if document is None:
            raise RightsError(
                f"{entry.right_id} cites {entry.source_id}, which is not in the corpus"
            )
        body = str(document.metadata.get("source_text", ""))
        if _normalise(entry.quote) not in _normalise(body):
            raise RightsError(
                f"{entry.right_id} quotes text that does not appear in {entry.source_id}. "
                "A right that is not in the law does not load."
            )
    return entries


def rights_for(
    entries: Sequence[RightEntry],
    domain: LegalDomain,
) -> tuple[RightEntry, ...]:
    """Rights for this domain, plus the legal-aid rights that apply to everyone."""

    return tuple(
        entry
        for entry in entries
        # Legal-aid entitlement is not a criminal or labour right, it is everyone's,
        # so it travels with every domain rather than being duplicated into each.
        if entry.domain is domain or entry.domain is LegalDomain.CONSTITUTIONAL
    )
