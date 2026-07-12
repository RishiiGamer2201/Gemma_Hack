"""Deterministic, offline pipeline from verified downloads to reviewable chunks.

This module performs no network I/O and makes no legal inference.  It accepts only
manifest-listed local artifacts whose download receipts match the actual bytes,
then labels every output chunk as pending human review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping

from .chunker import SectionChunk, chunk_sections
from .extract import extract_document
from .manifest import OfficialSource, SourceManifest, load_manifest


class CorpusBuildError(RuntimeError):
    """A bounded failure while validating or processing a local source."""


@dataclass(frozen=True, slots=True)
class SourceBuildResult:
    """Deterministic report entry for one successfully processed source."""

    source_id: str
    filename: str
    output_filename: str
    required: bool
    page_count: int
    chunk_count: int
    empty_page_count: int
    sha256: str
    parser: str


@dataclass(frozen=True, slots=True)
class SourceBuildFailure:
    """Deterministic report entry for one source that could not be processed."""

    source_id: str
    filename: str
    required: bool
    error: str
    page_count: int | None = None
    chunk_count: int | None = None
    empty_page_count: int | None = None
    sha256: str | None = None
    parser: str | None = None


@dataclass(frozen=True, slots=True)
class CorpusBuildReport:
    """Complete build outcome; callers use ``required_failures`` as exit status."""

    schema_version: int
    manifest_schema_version: int
    selected_source_ids: tuple[str, ...]
    successes: tuple[SourceBuildResult, ...]
    failures: tuple[SourceBuildFailure, ...]

    @property
    def required_failures(self) -> int:
        return sum(failure.required for failure in self.failures)

    def as_record(self) -> dict[str, Any]:
        """Return a JSON-ready record with deterministic key and item ordering."""

        return {
            "schema_version": self.schema_version,
            "manifest_schema_version": self.manifest_schema_version,
            "selected_source_ids": list(self.selected_source_ids),
            "summary": {
                "selected": len(self.selected_source_ids),
                "succeeded": len(self.successes),
                "failed": len(self.failures),
                "required_failures": self.required_failures,
            },
            "successes": [asdict(result) for result in self.successes],
            "failures": [asdict(failure) for failure in self.failures],
        }


def build_corpus(
    manifest_path: str | Path,
    raw_dir: str | Path,
    output_dir: str | Path,
    *,
    source_ids: Iterable[str] | None = None,
    allow_empty_pages: bool = False,
) -> CorpusBuildReport:
    """Build verified, review-pending JSONL chunks from local source files.

    Sources follow manifest order so repeated builds produce byte-identical JSONL
    and report files.  Individual failures are captured in ``build_report.json``;
    an invalid manifest or an unknown requested source ID is rejected immediately.
    """

    manifest = load_manifest(manifest_path)
    selected = _select_sources(manifest, source_ids)
    raw_path = Path(raw_dir)
    destination = Path(output_dir)
    successes: list[SourceBuildResult] = []
    failures: list[SourceBuildFailure] = []

    for source in selected:
        try:
            _remove_stale_output(destination, source)
            result = _build_source(
                source,
                raw_path,
                destination,
                allow_empty_pages=allow_empty_pages,
            )
        except Exception as exc:
            # Preserve a stable, user-presentable boundary while allowing all
            # selected sources to be audited in one offline run.
            message = str(exc).strip() or exc.__class__.__name__
            failures.append(
                SourceBuildFailure(
                    source_id=source.source_id,
                    filename=source.filename,
                    required=source.required,
                    error=message,
                )
            )
        else:
            successes.append(result)

    report = CorpusBuildReport(
        schema_version=1,
        manifest_schema_version=manifest.schema_version,
        selected_source_ids=tuple(source.source_id for source in selected),
        successes=tuple(successes),
        failures=tuple(failures),
    )
    _atomic_write_json(destination / "build_report.json", report.as_record())
    return report


def _select_sources(
    manifest: SourceManifest, source_ids: Iterable[str] | None
) -> tuple[OfficialSource, ...]:
    if source_ids is None:
        return manifest.sources
    requested = tuple(dict.fromkeys(item.strip() for item in source_ids if item.strip()))
    if not requested:
        raise CorpusBuildError("at least one non-empty source_id is required")
    known = {source.source_id: source for source in manifest.sources}
    unknown = sorted(set(requested) - known.keys())
    if unknown:
        raise CorpusBuildError("unknown source_id value(s): " + ", ".join(unknown))
    requested_set = set(requested)
    # Manifest order, not CLI order, is the canonical deterministic order.
    return tuple(source for source in manifest.sources if source.source_id in requested_set)


def _build_source(
    source: OfficialSource,
    raw_dir: Path,
    output_dir: Path,
    *,
    allow_empty_pages: bool,
) -> SourceBuildResult:
    source_path = raw_dir / source.filename
    receipt_path = source_path.with_suffix(source_path.suffix + ".receipt.json")
    digest, receipt = _verify_local_artifact(source, source_path, receipt_path)
    document = extract_document(source_path, parser=source.parser)
    page_count = len(document.pages)
    if page_count == 0:
        raise CorpusBuildError("extraction returned no pages")
    empty_page_count = sum(not page.text.strip() for page in document.pages)
    if empty_page_count and not allow_empty_pages:
        raise CorpusBuildError(
            f"extraction returned {empty_page_count} empty page(s); "
            "review or use --allow-empty-pages"
        )

    metadata = _source_metadata(source, receipt, digest, parser=document.parser)
    chunks = chunk_sections(document, source_id=source.source_id, metadata=metadata)
    if not chunks:
        raise CorpusBuildError("extraction produced no non-empty chunks")
    output_filename = f"{source.source_id}.jsonl"
    _atomic_write_jsonl(output_dir / output_filename, chunks)
    return SourceBuildResult(
        source_id=source.source_id,
        filename=source.filename,
        output_filename=output_filename,
        required=source.required,
        page_count=page_count,
        chunk_count=len(chunks),
        empty_page_count=empty_page_count,
        sha256=digest,
        parser=document.parser,
    )


def _verify_local_artifact(
    source: OfficialSource, source_path: Path, receipt_path: Path
) -> tuple[str, Mapping[str, Any]]:
    if not source_path.is_file():
        raise CorpusBuildError(f"source file is missing: {source.filename}")
    if not receipt_path.is_file():
        raise CorpusBuildError(f"download receipt is missing: {receipt_path.name}")
    try:
        receipt = _load_json_object(receipt_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusBuildError(f"invalid download receipt: {receipt_path.name}") from exc

    expected_fields = {
        "source_id": source.source_id,
        "filename": source.filename,
        "url": source.url,
        "official_landing_url": source.official_landing_url,
    }
    for field, expected in expected_fields.items():
        if receipt.get(field) != expected:
            raise CorpusBuildError(f"receipt {field} does not match the reviewed manifest")

    try:
        body = source_path.read_bytes()
    except OSError as exc:
        raise CorpusBuildError(f"could not read source file: {source.filename}") from exc
    digest = hashlib.sha256(body).hexdigest()
    receipt_digest = receipt.get("sha256")
    if not isinstance(receipt_digest, str) or receipt_digest.casefold() != digest:
        raise CorpusBuildError("receipt SHA-256 does not match the local source bytes")
    byte_count = receipt.get("byte_count")
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count != len(body):
        raise CorpusBuildError("receipt byte_count does not match the local source bytes")
    downloaded_at = receipt.get("downloaded_at")
    if not isinstance(downloaded_at, str) or not _is_datetime(downloaded_at):
        raise CorpusBuildError("receipt downloaded_at must be an ISO-8601 timestamp")
    return digest, receipt


def _remove_stale_output(output_dir: Path, source: OfficialSource) -> None:
    """Ensure a failed rebuild cannot leave an older source generation trusted."""

    output_path = output_dir / f"{source.source_id}.jsonl"
    try:
        output_path.unlink(missing_ok=True)
    except OSError as exc:
        raise CorpusBuildError(
            f"could not remove stale output before rebuild: {output_path.name}"
        ) from exc


def _source_metadata(
    source: OfficialSource,
    receipt: Mapping[str, Any],
    digest: str,
    *,
    parser: str,
) -> dict[str, Any]:
    """Copy reviewed facts into chunks without interpreting the legal text."""

    return {
        "act": source.title,
        "title": source.title,
        "jurisdiction": source.jurisdiction,
        "language": source.language,
        "document_type": source.document_type,
        "effective_from": source.effective_from.isoformat() if source.effective_from else None,
        "effective_to": source.effective_to.isoformat() if source.effective_to else None,
        "status": source.status,
        "priority": source.priority,
        "official_url": source.url,
        "official_landing_url": source.official_landing_url,
        "retrieved_at": receipt["downloaded_at"],
        "sha256": digest,
        "parser": parser,
        "parser_requested": source.parser,
        "ocr_used": False,
        "audit_status": "pending_human_review",
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    payload = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
    )
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def _is_datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _atomic_write_jsonl(path: Path, chunks: Iterable[SectionChunk]) -> None:
    lines = [
        json.dumps(
            chunk.as_record(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        for chunk in chunks
    ]
    _atomic_replace(path, "".join(line + "\n" for line in lines).encode("utf-8"))


def _atomic_write_json(path: Path, record: Mapping[str, Any]) -> None:
    data = (
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_replace(path, data)


def _atomic_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
