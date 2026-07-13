"""Shared retrieval value objects.

The objects deliberately retain the complete source metadata mapping.  Retrieval
code may rank evidence, but it must not discard provenance needed by later
citation and effective-date checks.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

DateLike = date | datetime | str
_PROFILE_ID = re.compile(r"^[a-z0-9_]+$")


def _freeze_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_metadata(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_metadata(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_metadata(item) for item in value)
    return value


def _as_date(value: DateLike | None, *, field_name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD)") from exc


@dataclass(frozen=True, slots=True)
class RetrievalDocument:
    """A searchable source chunk with immutable provenance metadata."""

    source_id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if not self.text.strip():
            raise ValueError("text must not be empty")
        # Copy first so callers cannot mutate provenance after indexing.
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Filters applied before ranking.

    ``effective_on`` selects material in force on that date. An absent
    ``effective_to`` means the source remains in force. Metadata dates must be
    ISO dates or ``date`` objects; malformed dates are excluded, not guessed.
    A document declaring ``applicability_profile_id`` is excluded unless that
    exact profile appears in ``applicability_profiles`` after a separate facts gate.

    Many Indian statutes commence "on such date as the Central Government may, by
    notification, appoint", so the act text alone cannot prove an effective date.
    Such a source records no ``effective_from`` and is excluded by default. Setting
    ``include_undated_sources`` admits it, but the caller then owes the user an
    explicit "commencement not verified" warning on every resulting citation: an
    undated source is *unproven*, not *proven current*.
    """

    jurisdiction: str | None = None
    language: str | None = None
    status: str | None = None
    act: str | None = None
    document_type: str | None = None
    effective_on: DateLike | None = None
    applicability_profiles: frozenset[str] = frozenset()
    include_undated_sources: bool = False

    def __post_init__(self) -> None:
        for field_name in ("jurisdiction", "language", "status", "act", "document_type"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{field_name} filter must be a string")
            if isinstance(value, str) and not value.strip():
                raise ValueError(f"{field_name} filter must not be blank")
        object.__setattr__(
            self,
            "effective_on",
            _as_date(self.effective_on, field_name="effective_on"),
        )
        if not isinstance(self.applicability_profiles, frozenset):
            raise TypeError("applicability_profiles must be a frozenset")
        if any(
            not isinstance(item, str) or not _PROFILE_ID.fullmatch(item)
            for item in self.applicability_profiles
        ):
            raise ValueError("applicability_profiles entries must be lowercase profile IDs")

    @staticmethod
    def _matches_text(actual: Any, expected: str | None) -> bool:
        if expected is None:
            return True
        if isinstance(actual, (list, tuple, set, frozenset)):
            return any(str(item).casefold() == expected.casefold() for item in actual)
        return actual is not None and str(actual).casefold() == expected.casefold()

    def matches(self, document: RetrievalDocument) -> bool:
        metadata = document.metadata
        if not self._matches_text(metadata.get("jurisdiction"), self.jurisdiction):
            return False
        if not self._matches_text(metadata.get("language"), self.language):
            return False
        if not self._matches_text(metadata.get("status"), self.status):
            return False
        if not self._matches_text(metadata.get("act"), self.act):
            return False
        if not self._matches_text(metadata.get("document_type"), self.document_type):
            return False
        profile = metadata.get("applicability_profile_id")
        if profile is not None:
            if not isinstance(profile, str) or profile not in self.applicability_profiles:
                return False

        if self.effective_on is None:
            return True
        try:
            effective_from = _as_date(
                metadata.get("effective_from"), field_name="metadata.effective_from"
            )
            effective_to = _as_date(
                metadata.get("effective_to"), field_name="metadata.effective_to"
            )
        except ValueError:
            return False
        if effective_from is None:
            # Legal applicability cannot be inferred when the start date is absent.
            # It may only be admitted where the caller has undertaken to label the
            # citation as having an unverified commencement date.
            return self.include_undated_sources
        return effective_from <= self.effective_on and (
            effective_to is None or self.effective_on <= effective_to
        )


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """A ranked result retaining its document and per-channel evidence."""

    document: RetrievalDocument
    score: float
    rank: int = 0
    channel_scores: Mapping[str, float] = field(default_factory=dict)
    channel_ranks: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "channel_scores", MappingProxyType(dict(self.channel_scores))
        )
        object.__setattr__(
            self, "channel_ranks", MappingProxyType(dict(self.channel_ranks))
        )

    @property
    def source_id(self) -> str:
        return self.document.source_id

    @property
    def text(self) -> str:
        return self.document.text

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self.document.metadata
