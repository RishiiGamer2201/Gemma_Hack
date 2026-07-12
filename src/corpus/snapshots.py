"""Restricted acquisition of reviewed official HTML source snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePath
import tempfile
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SnapshotError(RuntimeError):
    """A bounded manifest or network failure during snapshot acquisition."""


def _host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("snapshot URLs must be absolute HTTPS URLs")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("snapshot URLs must not contain credentials or fragments")
    return parsed.hostname.casefold().rstrip(".")


class SnapshotSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$", min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    url: str
    official_landing_url: str
    filename: str = Field(pattern=r"^[A-Za-z0-9_.-]+\.html$")
    category: str = Field(min_length=1, max_length=80)
    required_text: tuple[str, ...] = Field(min_length=1)
    allowed_hosts: tuple[str, ...] = Field(min_length=1)

    @field_validator("url", "official_landing_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _host(value)
        return value

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if PurePath(value).name != value:
            raise ValueError("filename must be a safe basename")
        return value

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(host.casefold().strip().rstrip(".") for host in value))
        if any(not host or "/" in host or ":" in host for host in normalized):
            raise ValueError("allowed_hosts must contain bare DNS hostnames")
        return normalized

    @model_validator(mode="after")
    def validate_hosts(self) -> "SnapshotSource":
        if _host(self.url) not in self.allowed_hosts or _host(self.official_landing_url) not in self.allowed_hosts:
            raise ValueError("snapshot and landing hosts must be explicitly allowed")
        return self


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: int = Field(default=1, ge=1)
    sources: Annotated[tuple[SnapshotSource, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique(self) -> "SnapshotManifest":
        ids = [source.source_id for source in self.sources]
        names = [source.filename.casefold() for source in self.sources]
        if len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise ValueError("snapshot source IDs and filenames must be unique")
        return self


@dataclass(frozen=True, slots=True)
class SnapshotReceipt:
    source_id: str
    title: str
    url: str
    official_landing_url: str
    retrieved_at: str
    content_type: str
    byte_count: int
    sha256: str


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def load_snapshot_manifest(path: str | Path) -> SnapshotManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return SnapshotManifest.model_validate(payload)


def download_snapshot(
    source: SnapshotSource,
    output_dir: str | Path,
    *,
    timeout: float = 45.0,
    max_bytes: int = 10 * 1024 * 1024,
    overwrite: bool = False,
) -> SnapshotReceipt:
    destination = Path(output_dir) / source.filename
    receipt_path = destination.with_suffix(".html.receipt.json")
    if not overwrite and (destination.exists() or receipt_path.exists()):
        raise FileExistsError(f"snapshot or receipt already exists: {destination.name}")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(source.url, headers={"User-Agent": "NyayaNavigatorCorpus/1.0"})
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
            if final_url != source.url or _host(final_url) not in source.allowed_hosts:
                raise SnapshotError("redirected or non-allowlisted snapshot response blocked")
            content_type = response.headers.get_content_type().casefold()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise SnapshotError(f"unexpected snapshot Content-Type: {content_type}")
            body = response.read(max_bytes + 1)
    except HTTPError as exc:
        raise SnapshotError(f"official snapshot returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise SnapshotError(f"could not retrieve official snapshot: {exc.reason}") from exc
    if len(body) > max_bytes:
        raise SnapshotError("snapshot exceeds configured byte limit")
    prefix = body[:4096].lower()
    if b"<html" not in prefix and b"<!doctype html" not in prefix:
        raise SnapshotError("response does not look like an HTML document")
    decoded = body.decode("utf-8", errors="replace").casefold()
    missing = [text for text in source.required_text if text.casefold() not in decoded]
    if missing:
        raise SnapshotError("snapshot is missing reviewed content markers: " + ", ".join(missing))
    digest = hashlib.sha256(body).hexdigest()
    receipt = SnapshotReceipt(
        source_id=source.source_id,
        title=source.title,
        url=source.url,
        official_landing_url=source.official_landing_url,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        content_type=content_type,
        byte_count=len(body),
        sha256=digest,
    )
    _atomic_write(destination, body)
    _atomic_write(
        receipt_path,
        (json.dumps(asdict(receipt), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return receipt


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
