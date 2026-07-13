"""Reviewed, effective-date-aware IPC/BNS mapping contracts and lookup.

The module never derives a mapping from section-number similarity.  Every result
comes from an explicitly supplied, source-backed ``LegalMapping`` record, and every
lookup returns collections of provisions because a relationship may be split,
merged, partial, omitted, or have no direct equivalent.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import Field, HttpUrl, model_validator

from src.models.schemas import NonEmptyText, ShortText, StrictModel

BNS_EFFECTIVE_DATE = date(2024, 7, 1)


class LegalCode(StrEnum):
    """Criminal codes represented by the initial temporal mapping catalogue."""

    IPC = "IPC"
    BNS = "BNS"


class MappingType(StrEnum):
    """A reviewed characterization of an old/new-law relationship."""

    EXACT = "exact"
    PARTIAL = "partial"
    SPLIT = "split"
    MERGED = "merged"
    OMITTED = "omitted"
    NO_DIRECT_EQUIVALENT = "no_direct_equivalent"


class ProvisionReference(StrictModel):
    """One provision in a mapping; it is not itself a legal conclusion."""

    code: LegalCode
    section: Annotated[str, Field(min_length=1, max_length=60)]
    title: ShortText | None = None


class LegalMapping(StrictModel):
    """A human-reviewed relationship supported by an official source."""

    mapping_id: Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")]
    source_provisions: Annotated[tuple[ProvisionReference, ...], Field(min_length=1)]
    target_provisions: tuple[ProvisionReference, ...] = ()
    mapping_type: MappingType
    offence_names: Annotated[tuple[ShortText, ...], Field(min_length=1)]
    aliases: tuple[ShortText, ...] = ()
    plain_language_description: NonEmptyText
    change_notes: NonEmptyText
    official_source_url: HttpUrl
    official_source_id: Annotated[str, Field(min_length=1, max_length=200)]
    reviewed_by: ShortText
    reviewed_at: date
    target_effective_from: date = BNS_EFFECTIVE_DATE
    incident_date_required: bool = True

    @model_validator(mode="after")
    def validate_relationship_shape(self) -> LegalMapping:
        if any(item.code is not LegalCode.IPC for item in self.source_provisions):
            raise ValueError("source_provisions must contain reviewed IPC provisions")
        if any(item.code is not LegalCode.BNS for item in self.target_provisions):
            raise ValueError("target_provisions must contain reviewed BNS provisions")
        if self.mapping_type in {
            MappingType.OMITTED,
            MappingType.NO_DIRECT_EQUIVALENT,
        } and self.target_provisions:
            raise ValueError(f"{self.mapping_type.value} mappings cannot claim target provisions")
        if self.mapping_type not in {
            MappingType.OMITTED,
            MappingType.NO_DIRECT_EQUIVALENT,
        } and not self.target_provisions:
            raise ValueError(f"{self.mapping_type.value} mappings require reviewed target provisions")
        if self.mapping_type is MappingType.EXACT and (
            len(self.source_provisions) != 1 or len(self.target_provisions) != 1
        ):
            raise ValueError("an exact mapping must explicitly contain one source and one target")
        if self.mapping_type is MappingType.SPLIT and (
            len(self.source_provisions) != 1 or len(self.target_provisions) < 2
        ):
            raise ValueError("a split mapping requires one source and at least two targets")
        if self.mapping_type is MappingType.MERGED and len(self.source_provisions) < 2:
            raise ValueError("a merged mapping requires at least two source provisions")
        if not self.incident_date_required:
            raise ValueError("incident_date_required must remain true for IPC/BNS applicability")
        return self


class MappingLookupStatus(StrEnum):
    """Whether a lookup is informational or date-routed."""

    NOT_FOUND = "not_found"
    INCIDENT_DATE_REQUIRED = "incident_date_required"
    HISTORICAL_IPC = "historical_ipc"
    CURRENT_BNS = "current_bns"


class MappingLookupResult(StrictModel):
    """Result that preserves all candidates and exposes date uncertainty."""

    query: NonEmptyText
    status: MappingLookupStatus
    candidates: tuple[LegalMapping, ...] = ()
    applicable_provisions: tuple[ProvisionReference, ...] = ()
    historical_provisions: tuple[ProvisionReference, ...] = ()
    current_provisions: tuple[ProvisionReference, ...] = ()
    incident_date: date | None = None
    requires_incident_date_clarification: bool = False
    warning: NonEmptyText


class MappingCatalog:
    """Immutable in-memory catalogue of curated mappings with deterministic lookup."""

    def __init__(self, mappings: Iterable[LegalMapping]) -> None:
        records = tuple(mappings)
        ids = [record.mapping_id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("mapping_id values must be unique")
        self._mappings = records

    @property
    def mappings(self) -> tuple[LegalMapping, ...]:
        """Return the reviewed records without exposing mutable catalogue state."""

        return self._mappings

    def lookup(self, query: str, *, incident_date: date | None = None) -> MappingLookupResult:
        """Find reviewed mappings and route provisions using the incident date.

        A missing date intentionally produces no ``applicable_provisions``.  Callers
        may show historical and current alternatives but must ask the user for the
        date before applying either code to their situation.
        """

        normalized = _normalize(query)
        if not normalized:
            raise ValueError("mapping lookup query cannot be blank")

        candidates = tuple(record for record in self._mappings if _matches(record, normalized))
        historical = _unique_provisions(
            provision for record in candidates for provision in record.source_provisions
        )
        current = _unique_provisions(
            provision for record in candidates for provision in record.target_provisions
        )

        if not candidates:
            return MappingLookupResult(
                query=query,
                status=MappingLookupStatus.NOT_FOUND,
                warning="No reviewed IPC/BNS mapping matched this query; do not infer one from section numbers.",
            )
        if incident_date is None:
            return MappingLookupResult(
                query=query,
                status=MappingLookupStatus.INCIDENT_DATE_REQUIRED,
                candidates=candidates,
                historical_provisions=historical,
                current_provisions=current,
                requires_incident_date_clarification=True,
                warning=(
                    "The incident date is required before selecting IPC or BNS. "
                    "The alternatives shown are informational and may not be one-to-one."
                ),
            )

        use_current = all(incident_date >= record.target_effective_from for record in candidates)
        applicable = current if use_current else historical
        status = MappingLookupStatus.CURRENT_BNS if use_current else MappingLookupStatus.HISTORICAL_IPC
        warning = (
            "Date routing selected reviewed BNS provisions; mapping notes and official evidence still govern."
            if use_current
            else "Date routing selected historical IPC provisions; later procedural events may require separate review."
        )
        return MappingLookupResult(
            query=query,
            status=status,
            candidates=candidates,
            applicable_provisions=applicable,
            historical_provisions=historical,
            current_provisions=current,
            incident_date=incident_date,
            warning=warning,
        )


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _matches(record: LegalMapping, normalized_query: str) -> bool:
    explicit_references = _extract_explicit_references(normalized_query)
    if explicit_references:
        provision_references = {
            (item.code.value.casefold(), _normalize(item.section))
            for item in (*record.source_provisions, *record.target_provisions)
        }
        return any(reference in provision_references for reference in explicit_references)

    section_only = re.fullmatch(r"section\s+(\d+[a-z]?)", normalized_query)
    if section_only:
        wanted = section_only.group(1)
        return any(
            _normalize(item.section) == wanted
            for item in (*record.source_provisions, *record.target_provisions)
        )

    terms = [
        record.mapping_id,
        record.plain_language_description,
        *record.offence_names,
        *record.aliases,
        *(f"{item.code.value} {item.section}" for item in record.source_provisions),
        *(f"{item.code.value} {item.section}" for item in record.target_provisions),
        *(f"section {item.section}" for item in record.source_provisions),
        *(f"section {item.section}" for item in record.target_provisions),
    ]
    normalized_terms = {_normalize(term) for term in terms}
    return any(
        normalized_query == term
        or (len(normalized_query) >= 4 and normalized_query in term)
        or (len(term) >= 4 and term in normalized_query)
        for term in normalized_terms
    )


def _extract_explicit_references(normalized_query: str) -> set[tuple[str, str]]:
    """Extract code/section pairs without allowing numeric-prefix matches.

    Fuzzy substring matching is useful for offence aliases, but unsafe for legal
    identifiers: IPC 42 must never match IPC 420. Explicit identifiers therefore
    take a strict, boundary-aware path before descriptive matching.
    """

    return {
        (match.group(1).casefold(), match.group(2).casefold())
        for match in re.finditer(
            r"\b(ipc|bns)(?:\s+section)?\s+(\d+[a-z]?)\b",
            normalized_query,
        )
    }


def _unique_provisions(provisions: Iterable[ProvisionReference]) -> tuple[ProvisionReference, ...]:
    seen: set[tuple[LegalCode, str]] = set()
    unique: list[ProvisionReference] = []
    for provision in provisions:
        key = (provision.code, provision.section.casefold())
        if key not in seen:
            seen.add(key)
            unique.append(provision)
    return tuple(unique)
