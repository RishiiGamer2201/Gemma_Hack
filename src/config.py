"""Environment-backed settings for the offline prototype."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when configuration would violate an offline safety boundary."""


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive")
    return value


def ensure_loopback_url(url: str) -> str:
    """Validate that an inference URL cannot send user data off device."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ConfigurationError("Local inference URL must use http or https")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ConfigurationError("Local inference URL must use a loopback host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigurationError("Local inference URL must not include credentials or parameters")
    return url.rstrip("/")


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration with conservative local defaults."""

    ollama_url: str
    ollama_model: str
    max_context_tokens: int
    max_output_tokens: int
    corpus_path: Path
    index_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            ollama_url=ensure_loopback_url(
                os.getenv("NYAYA_OLLAMA_URL", "http://127.0.0.1:11434")
            ),
            ollama_model=os.getenv("NYAYA_OLLAMA_MODEL", "gemma4:e4b").strip(),
            max_context_tokens=_positive_int("NYAYA_MAX_CONTEXT_TOKENS", 4096),
            max_output_tokens=_positive_int("NYAYA_MAX_OUTPUT_TOKENS", 1200),
            corpus_path=Path(os.getenv("NYAYA_CORPUS_PATH", "data/processed/sections")),
            index_path=Path(os.getenv("NYAYA_INDEX_PATH", "data/indexes")),
        )
