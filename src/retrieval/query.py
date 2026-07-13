"""Deterministic, reviewed query expansion for offline retrieval.

This module contains vocabulary aliases only. It does not assert that statutes or
sections are legally equivalent. IPC/BNS aliases are accepted solely from the
caller after human review.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .tokenize import tokenize

# Small product vocabulary reviewed for retrieval recall. These are ordinary-language
# translations/synonyms, not legal definitions or statute mappings.
REVIEWED_LEGAL_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("arrest", "गिरफ्तारी", "giraftari"),
    ("complaint", "शिकायत", "shikayat"),
    ("tenant", "किरायेदार", "kirayedar"),
    ("wages", "वेतन", "vetan"),
    ("notice", "नोटिस"),
)


def _canonical_alias_key(value: str) -> str:
    # Treat common act/section separators as spaces while preserving identifiers
    # such as 125-A, where the hyphen is part of the section itself.
    normalized = re.sub(r"(?<=[A-Za-z])[-_:](?=\d)", " ", value)
    return " ".join(tokenize(normalized))


@dataclass(frozen=True, slots=True)
class QueryExpansion:
    original_terms: tuple[str, ...]
    expanded_terms: tuple[str, ...]
    query: str


def _canonical_aliases(
    aliases: Mapping[str, Sequence[str]] | None,
) -> Mapping[str, tuple[str, ...]]:
    canonical: dict[str, tuple[str, ...]] = {}
    for key, values in (aliases or {}).items():
        if not isinstance(key, str):
            raise TypeError("reviewed alias keys must be strings")
        if isinstance(values, (str, bytes)):
            raise TypeError("reviewed alias values must be a sequence of strings")
        canonical_key = _canonical_alias_key(key)
        if not canonical_key:
            raise ValueError("reviewed alias keys must contain searchable text")
        normalized_values: list[str] = []
        for value in values:
            if not isinstance(value, str):
                raise TypeError("reviewed alias values must be strings")
            terms = tokenize(value)
            if not terms:
                raise ValueError("reviewed alias values must contain searchable text")
            normalized_values.extend(terms)
        if not normalized_values:
            raise ValueError("reviewed aliases must contain at least one value")
        if canonical_key in canonical:
            raise ValueError("reviewed alias keys must be unique after normalization")
        canonical[canonical_key] = tuple(dict.fromkeys(normalized_values))
    return MappingProxyType(dict(sorted(canonical.items())))


class QueryExpander:
    """Expand query terms from fixed synonyms and caller-reviewed aliases."""

    def __init__(
        self,
        *,
        synonym_groups: Iterable[Sequence[str]] = REVIEWED_LEGAL_SYNONYM_GROUPS,
        reviewed_mapping_aliases: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        groups: list[tuple[str, ...]] = []
        for group in synonym_groups:
            if isinstance(group, (str, bytes)):
                raise TypeError("synonym groups must be sequences of strings")
            items = tuple(group)
            if any(not isinstance(item, str) for item in items):
                raise TypeError("synonym group values must be strings")
            terms = tuple(dict.fromkeys(term for item in items for term in tokenize(item)))
            if len(terms) > 1:
                groups.append(terms)
        self.synonym_groups = tuple(groups)
        self.reviewed_mapping_aliases = _canonical_aliases(reviewed_mapping_aliases)

    def expand(self, query: str) -> QueryExpansion:
        original = tuple(tokenize(query))
        expanded = list(original)
        present = set(original)
        for group in self.synonym_groups:
            if present.intersection(group):
                expanded.extend(group)

        padded_query = f" {_canonical_alias_key(query)} "
        for key, aliases in self.reviewed_mapping_aliases.items():
            if f" {key} " in padded_query:
                expanded.extend(aliases)

        unique = tuple(dict.fromkeys(expanded))
        return QueryExpansion(
            original_terms=original,
            expanded_terms=unique,
            query=" ".join(unique),
        )
