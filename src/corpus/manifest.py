"""Validated manifest models for reviewed official sources."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path, PurePath
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ParserName = Literal["text", "pypdf", "pymupdf", "auto"]
ChunkingStrategy = Literal["statute_sections", "gazette_rules_en"]
SourceStatus = Literal["in_force", "historical", "repealed", "unknown"]
SourceRelationship = Literal["principal", "amendment", "corrigendum"]


def _https_host(value: str, *, field_name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"{field_name} must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"{field_name} must not contain credentials or a fragment")
    return parsed.hostname.casefold().rstrip(".")


class OfficialSource(BaseModel):
    """One explicitly reviewed source and its per-record network allowlist."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$", min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    url: str
    official_landing_url: str
    filename: str = Field(min_length=1, max_length=240)
    language: str = Field(min_length=2, max_length=40)
    jurisdiction: str = Field(min_length=1, max_length=120)
    document_type: str = Field(min_length=1, max_length=80)
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: SourceStatus = "unknown"
    priority: int = Field(default=3, ge=1, le=5)
    parser: ParserName = "auto"
    chunking_strategy: ChunkingStrategy = "statute_sections"
    relationship: SourceRelationship = "principal"
    modifies_source_ids: tuple[str, ...] = ()
    target_instrument_title: str | None = Field(default=None, max_length=500)
    gazette_reference: str | None = Field(default=None, max_length=160)
    review_note: str | None = Field(default=None, max_length=1000)
    required: bool = True
    allowed_hosts: tuple[str, ...] = Field(min_length=1)

    @field_validator("url", "official_landing_url")
    @classmethod
    def validate_https_url(cls, value: str, info) -> str:  # type: ignore[no-untyped-def]
        _https_host(value, field_name=info.field_name)
        return value

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if PurePath(value).name != value or value in {".", ".."}:
            raise ValueError("filename must be a safe basename")
        device_stem = value.split(".", 1)[0].upper()
        reserved = {"CON", "PRN", "AUX", "NUL"} | {
            f"{prefix}{number}"
            for prefix in ("COM", "LPT")
            for number in range(1, 10)
        }
        if device_stem in reserved:
            raise ValueError("filename uses a Windows reserved device name")
        if not value.casefold().endswith((".pdf", ".txt")):
            raise ValueError("filename must identify a PDF or text file")
        return value

    @field_validator("source_id")
    @classmethod
    def validate_source_id_filename_safety(cls, value: str) -> str:
        device_stem = value.split(".", 1)[0].upper()
        reserved = {"CON", "PRN", "AUX", "NUL"} | {
            f"{prefix}{number}"
            for prefix in ("COM", "LPT")
            for number in range(1, 10)
        }
        if device_stem in reserved:
            raise ValueError("source_id uses a Windows reserved device name")
        return value

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for host in value:
            parsed_host = host.casefold().strip().rstrip(".")
            if not parsed_host or ":" in parsed_host or "/" in parsed_host:
                raise ValueError("allowed_hosts entries must be bare DNS hostnames")
            if parsed_host not in normalized:
                normalized.append(parsed_host)
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_record(self) -> OfficialSource:
        download_host = _https_host(self.url, field_name="url")
        landing_host = _https_host(
            self.official_landing_url, field_name="official_landing_url"
        )
        if download_host not in self.allowed_hosts:
            raise ValueError("url host is absent from this source's allowed_hosts")
        if landing_host not in self.allowed_hosts:
            raise ValueError(
                "official_landing_url host is absent from this source's allowed_hosts"
            )
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be earlier than effective_from")
        if self.filename.casefold().endswith(".txt") and self.parser != "text":
            raise ValueError("text files require parser='text'")
        if self.relationship == "principal" and (
            self.modifies_source_ids or self.target_instrument_title
        ):
            raise ValueError("principal sources cannot declare modification targets")
        if self.relationship != "principal" and (
            not self.modifies_source_ids or not self.target_instrument_title
        ):
            raise ValueError(
                "amendments and corrigenda require modifies_source_ids and "
                "target_instrument_title"
            )
        if self.source_id in self.modifies_source_ids:
            raise ValueError("a source cannot modify itself")
        return self

    def allows_url(self, value: str) -> bool:
        try:
            return _https_host(value, field_name="url") in self.allowed_hosts
        except ValueError:
            return False


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    sources: tuple[OfficialSource, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_uniqueness(self) -> SourceManifest:
        ids = [source.source_id for source in self.sources]
        filenames = [source.filename.casefold() for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("manifest source_id values must be unique")
        if len(filenames) != len(set(filenames)):
            raise ValueError("manifest filenames must be unique")
        known = set(ids)
        by_id = {source.source_id: source for source in self.sources}
        for source in self.sources:
            unknown = sorted(set(source.modifies_source_ids) - known)
            if unknown:
                raise ValueError(
                    f"{source.source_id} modifies unknown source_id value(s): "
                    + ", ".join(unknown)
                )
            non_principal_targets = [
                target
                for target in source.modifies_source_ids
                if by_id[target].relationship != "principal"
            ]
            if non_principal_targets:
                raise ValueError(
                    f"{source.source_id} modification targets must be principal sources: "
                    + ", ".join(non_principal_targets)
                )
        return self


def load_manifest(path: str | Path) -> SourceManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read manifest: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest is not valid JSON: {manifest_path}") from exc
    return SourceManifest.model_validate(payload)
