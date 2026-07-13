"""Unicode-aware legal text tokenization without external dependencies."""

from __future__ import annotations

import unicodedata

# Characters commonly internal to citations and section identifiers. Parentheses
# are handled separately so ``316(2)(a)`` remains one token.
_INTERNAL = frozenset({".", "/", "-", "_", ":"})


def _is_word_character(character: str) -> bool:
    return unicodedata.category(character)[0] in {"L", "M", "N"}


def tokenize(text: str) -> list[str]:
    """Return deterministic, case-folded tokens.

    Unicode letters, combining marks and digits are retained. Legal identifiers
    such as ``316(2)(a)``, ``125-A`` and ``Crl.A.123/2024`` remain intact while
    surrounding prose punctuation is removed.
    """

    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    current: list[str] = []
    index = 0

    def flush() -> None:
        if current and any(_is_word_character(char) for char in current):
            tokens.append("".join(current))
        current.clear()

    while index < len(normalized):
        character = normalized[index]
        if _is_word_character(character):
            current.append(character)
            index += 1
            continue

        # A closed subsection remains part of the identifier, allowing chained
        # forms such as ``316(2)(a)``.
        previous_is_word = bool(
            current and (_is_word_character(current[-1]) or current[-1] == ")")
        )
        next_is_word = index + 1 < len(normalized) and _is_word_character(
            normalized[index + 1]
        )
        if character in _INTERNAL and previous_is_word and next_is_word:
            current.append(character)
            index += 1
            continue

        if character == "(" and previous_is_word:
            close = normalized.find(")", index + 1)
            if close != -1:
                inside = normalized[index + 1 : close]
                if inside and all(_is_word_character(char) for char in inside):
                    current.extend(normalized[index : close + 1])
                    index = close + 1
                    continue

        flush()
        index += 1

    flush()
    return tokens
