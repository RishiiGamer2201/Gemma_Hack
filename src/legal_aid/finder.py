"""Deterministic, offline lookup for the reviewed legal-aid directory."""

from __future__ import annotations

import json
import unicodedata
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.legal_aid.directory import LegalAidContact, LegalAidFallback
from src.models.schemas import StrictModel


class LegalAidFinderError(RuntimeError):
    """A bounded directory loading or validation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MatchStatus(StrEnum):
    MATCHED = "matched"
    UNMATCHED_DELHI = "unmatched_delhi"
    OUTSIDE_DELHI = "outside_delhi"
    UNKNOWN_LOCATION = "unknown_location"


class NormalizedLegalAidQuery(StrictModel):
    district_or_city: str
    state: str | None = None


class SourceFreshness(StrictModel):
    directory_filename: str
    record_count: int
    oldest_verified_date: date | None
    newest_verified_date: date | None
    source_sha256: tuple[str, ...]


class LegalAidSearchResult(StrictModel):
    match_status: MatchStatus
    normalized_query: NormalizedLegalAidQuery
    contacts: tuple[LegalAidContact, ...]
    fallbacks: tuple[LegalAidFallback, ...]
    warnings: tuple[str, ...]
    source_freshness: SourceFreshness


_MAX_DIRECTORY_BYTES = 2 * 1024 * 1024
_TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "contacts", "fallbacks", "state_contacts"}
)
_REQUIRED_FALLBACKS = {
    "nalsa-15100": "15100",
    "tele-law-14454": "14454",
}
_DELHI_STATE_ALIASES = frozenset(
    {
        "delhi",
        "delhi nct",
        "nct delhi",
        "nct of delhi",
        "national capital territory delhi",
        "national capital territory of delhi",
    }
)

# These aliases are deliberately finite. The finder never applies edit distance,
# token similarity, or a model-generated guess to a district name.
_DISTRICT_ALIASES = {
    "central": "central",
    "central delhi": "central",
    "central district": "central",
    "central ii": "central ii",
    "central 2": "central ii",
    "central ii delhi": "central ii",
    "rouse avenue": "central ii",
    "rouse avenue delhi": "central ii",
    "rouse avenue court": "central ii",
    "east": "east",
    "east delhi": "east",
    "new delhi": "new delhi",
    "new delhi district": "new delhi",
    "north": "north",
    "north delhi": "north",
    "north east": "north east",
    "northeast": "north east",
    "north east delhi": "north east",
    "northeast delhi": "north east",
    "north west": "north west",
    "northwest": "north west",
    "north west delhi": "north west",
    "northwest delhi": "north west",
    "shahdara": "shahdara",
    "shahdara delhi": "shahdara",
    "south": "south",
    "south delhi": "south",
    "south east": "south east",
    "southeast": "south east",
    "south east delhi": "south east",
    "southeast delhi": "south east",
    "south west": "south west",
    "southwest": "south west",
    "south west delhi": "south west",
    "southwest delhi": "south west",
    "west": "west",
    "west delhi": "west",
}


def normalize_location(value: str) -> str:
    """Normalize case, Unicode, punctuation, and whitespace without guessing."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    characters = [
        character if unicodedata.category(character)[0] in {"L", "N"} else " "
        for character in normalized
    ]
    return " ".join("".join(characters).split())


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LegalAidFinderError("duplicate_key", f"duplicate JSON key: {key}")
        result[key] = value
    return result


class LegalAidFinder:
    """Load and query a verified local directory without any network capability."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        payload = self._load_payload(self.directory)
        self.contacts = self._validate_contacts(payload["contacts"])
        self.fallbacks = self._validate_fallbacks(payload["fallbacks"])
        # State authorities are a separate tier. A citizen outside Delhi used to get
        # only the national helpline; now they get the authority for their own state.
        self.state_contacts = self._validate_contacts(payload.get("state_contacts", []))
        self._contacts_by_district = self._index_contacts(self.contacts)
        self._contacts_by_state = {
            normalize_location(contact.state): contact for contact in self.state_contacts
        }
        self.source_freshness = self._freshness()

    @staticmethod
    def _load_payload(path: Path) -> dict[str, Any]:
        try:
            size = path.stat().st_size
            if size > _MAX_DIRECTORY_BYTES:
                raise LegalAidFinderError(
                    "directory_too_large", "legal-aid directory exceeds the local size limit"
                )
            text = path.read_text(encoding="utf-8")
        except LegalAidFinderError:
            raise
        except (OSError, UnicodeError) as exc:
            raise LegalAidFinderError(
                "directory_unreadable", "could not read the local legal-aid directory"
            ) from exc
        try:
            payload = json.loads(text, object_pairs_hook=_unique_object)
        except LegalAidFinderError:
            raise
        except json.JSONDecodeError as exc:
            raise LegalAidFinderError(
                "invalid_json", "legal-aid directory is not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise LegalAidFinderError("invalid_shape", "directory root must be an object")
        unknown = set(payload) - _TOP_LEVEL_KEYS
        missing = _TOP_LEVEL_KEYS - set(payload)
        if unknown:
            raise LegalAidFinderError(
                "unknown_keys", f"unknown top-level keys: {', '.join(sorted(unknown))}"
            )
        if missing:
            raise LegalAidFinderError(
                "missing_keys", f"missing top-level keys: {', '.join(sorted(missing))}"
            )
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise LegalAidFinderError("unsupported_schema", "schema_version must equal 1")
        if not isinstance(payload["contacts"], list) or not isinstance(
            payload["fallbacks"], list
        ):
            raise LegalAidFinderError(
                "invalid_shape", "contacts and fallbacks must both be JSON arrays"
            )
        if not isinstance(payload.get("state_contacts", []), list):
            raise LegalAidFinderError(
                "invalid_shape", "state_contacts must be a JSON array"
            )
        return payload

    @staticmethod
    def _validate_contacts(records: list[Any]) -> tuple[LegalAidContact, ...]:
        contacts: list[LegalAidContact] = []
        try:
            contacts = [LegalAidContact.model_validate(record) for record in records]
        except ValidationError as exc:
            raise LegalAidFinderError(
                "invalid_contact", "a directory contact failed schema validation"
            ) from exc
        ids = [contact.contact_id for contact in contacts]
        if len(ids) != len(set(ids)):
            raise LegalAidFinderError("duplicate_contact", "duplicate contact_id detected")
        return tuple(contacts)

    @staticmethod
    def _validate_fallbacks(records: list[Any]) -> tuple[LegalAidFallback, ...]:
        try:
            fallbacks = tuple(LegalAidFallback.model_validate(record) for record in records)
        except ValidationError as exc:
            raise LegalAidFinderError(
                "invalid_fallback", "a directory fallback failed schema validation"
            ) from exc
        ids = [fallback.fallback_id for fallback in fallbacks]
        if len(ids) != len(set(ids)):
            raise LegalAidFinderError("duplicate_fallback", "duplicate fallback_id detected")
        by_id = {fallback.fallback_id: fallback for fallback in fallbacks}
        missing = sorted(set(_REQUIRED_FALLBACKS) - set(by_id))
        if missing:
            raise LegalAidFinderError(
                "missing_required_fallback",
                "missing required fallback IDs: " + ", ".join(missing),
            )
        for fallback_id, expected_phone in _REQUIRED_FALLBACKS.items():
            fallback = by_id[fallback_id]
            if fallback.phone != expected_phone or normalize_location(fallback.scope) != "india":
                raise LegalAidFinderError(
                    "invalid_required_fallback",
                    f"required fallback {fallback_id} has unreviewed phone or scope",
                )
        return fallbacks

    @staticmethod
    def _index_contacts(
        contacts: tuple[LegalAidContact, ...],
    ) -> dict[str, LegalAidContact]:
        index: dict[str, LegalAidContact] = {}
        for contact in contacts:
            if normalize_location(contact.state) not in _DELHI_STATE_ALIASES:
                raise LegalAidFinderError(
                    "unexpected_contact_scope",
                    "Delhi directory contains a contact outside the reviewed state scope",
                )
            if contact.district is None:
                raise LegalAidFinderError(
                    "missing_district", "Delhi directory contact has no district"
                )
            district = normalize_location(contact.district)
            if district in index:
                raise LegalAidFinderError(
                    "duplicate_district", "duplicate normalized district detected"
                )
            index[district] = contact
        return index

    def _freshness(self) -> SourceFreshness:
        records = (*self.contacts, *self.state_contacts, *self.fallbacks)
        dates = [record.verified_date for record in records]
        hashes = tuple(sorted({record.source_sha256 for record in records}))
        return SourceFreshness(
            directory_filename=self.directory.name,
            record_count=len(records),
            oldest_verified_date=min(dates) if dates else None,
            newest_verified_date=max(dates) if dates else None,
            source_sha256=hashes,
        )

    def _universal_fallbacks(self) -> tuple[LegalAidFallback, ...]:
        universal_scopes = {"india", "all india", "national", "universal"}
        return tuple(
            fallback
            for fallback in self.fallbacks
            if normalize_location(fallback.scope) in universal_scopes
            or "nalsa" in normalize_location(fallback.service).split()
        )

    def find(self, district_or_city: str, *, state: str | None = None) -> LegalAidSearchResult:
        district = normalize_location(district_or_city)
        normalized_state = normalize_location(state) if state is not None else None
        if not district:
            raise LegalAidFinderError(
                "invalid_query", "district or city must contain at least one letter or number"
            )
        if state is not None and not normalized_state:
            raise LegalAidFinderError(
                "invalid_query", "state must contain at least one letter or number"
            )

        normalized_query = NormalizedLegalAidQuery(
            district_or_city=district,
            state=normalized_state,
        )
        universal = self._universal_fallbacks()
        if normalized_state is not None and normalized_state not in _DELHI_STATE_ALIASES:
            state_contact = self._contacts_by_state.get(normalized_state)
            if state_contact is not None:
                return LegalAidSearchResult(
                    match_status=MatchStatus.OUTSIDE_DELHI,
                    normalized_query=normalized_query,
                    contacts=(state_contact,),
                    fallbacks=universal,
                    warnings=(
                        "Only Delhi has district-level contacts in this build. This is "
                        "the State Legal Services Authority for your state, which can "
                        "direct you to your district authority.",
                    ),
                    source_freshness=self.source_freshness,
                )
            return LegalAidSearchResult(
                match_status=MatchStatus.OUTSIDE_DELHI,
                normalized_query=normalized_query,
                contacts=(),
                fallbacks=universal,
                warnings=(
                    "The local district directory covers Delhi only; nationwide fallbacks are shown.",
                ),
                source_freshness=self.source_freshness,
            )

        canonical = _DISTRICT_ALIASES.get(district)
        contact = self._contacts_by_district.get(canonical) if canonical else None
        if contact is not None:
            return LegalAidSearchResult(
                match_status=MatchStatus.MATCHED,
                normalized_query=normalized_query,
                contacts=(contact,),
                fallbacks=universal,
                warnings=(),
                source_freshness=self.source_freshness,
            )

        is_explicit_delhi = normalized_state in _DELHI_STATE_ALIASES
        warning = (
            "No exact reviewed Delhi district match was found; no district contact was selected."
            if is_explicit_delhi
            else "State was not provided and the location did not match a reviewed Delhi alias."
        )
        return LegalAidSearchResult(
            match_status=(
                MatchStatus.UNMATCHED_DELHI
                if is_explicit_delhi
                else MatchStatus.UNKNOWN_LOCATION
            ),
            normalized_query=normalized_query,
            contacts=(),
            fallbacks=universal,
            warnings=(warning,),
            source_freshness=self.source_freshness,
        )
