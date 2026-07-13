"""Restricted downloader for explicitly reviewed official documents."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .manifest import OfficialSource


class DownloadError(RuntimeError):
    """A bounded and user-presentable acquisition failure."""


@dataclass(frozen=True, slots=True)
class DownloadReceipt:
    source_id: str
    filename: str
    url: str
    official_landing_url: str
    downloaded_at: str
    byte_count: int
    sha256: str
    content_type: str


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _atomic_write(path: Path, data: bytes, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing file: {path}")
        if overwrite:
            os.replace(temporary_name, path)
        else:
            # Hard-linking is an atomic create-if-absent operation on the same
            # filesystem; unlike os.replace it cannot clobber a racing writer.
            os.link(temporary_name, path)
            os.unlink(temporary_name)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def download_source(
    source: OfficialSource,
    output_dir: str | Path,
    *,
    timeout: float = 45.0,
    max_bytes: int = 50 * 1024 * 1024,
    overwrite: bool = False,
) -> DownloadReceipt:
    """Download one manifest-approved source without following redirects."""

    if timeout <= 0 or max_bytes <= 0:
        raise ValueError("timeout and max_bytes must be positive")
    if not source.allows_url(source.url):
        raise DownloadError("source URL is not allowed by its manifest record")

    destination = Path(output_dir) / source.filename
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    receipt_path = destination.with_suffix(destination.suffix + ".receipt.json")
    if not overwrite:
        existing = [path for path in (destination, checksum_path, receipt_path) if path.exists()]
        if existing:
            raise FileExistsError(f"refusing to overwrite existing artifact: {existing[0]}")

    request = Request(
        source.url,
        headers={
            "Accept": "application/pdf,text/plain;q=0.8",
            "User-Agent": "NyayaNavigatorCorpus/0.1 (offline legal research prototype)",
        },
        method="GET",
    )
    opener = build_opener(ProxyHandler({}), _NoRedirects())
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
            if final_url != source.url or not source.allows_url(final_url):
                raise DownloadError("redirected or non-allowlisted response URL blocked")
            content_type = response.headers.get_content_type().casefold()
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    declared_bytes = int(declared)
                    if declared_bytes < 0:
                        raise DownloadError("negative Content-Length received")
                    if declared_bytes > max_bytes:
                        raise DownloadError("response exceeds configured byte limit")
                except ValueError as exc:
                    raise DownloadError("invalid Content-Length received") from exc
            body = response.read(max_bytes + 1)
    except DownloadError:
        raise
    except HTTPError as exc:
        raise DownloadError(f"official source returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise DownloadError(f"could not retrieve official source: {exc}") from exc

    if len(body) > max_bytes:
        raise DownloadError("response exceeds configured byte limit")
    is_pdf = source.filename.casefold().endswith(".pdf")
    if is_pdf:
        if content_type not in {"application/pdf", "application/x-pdf"}:
            raise DownloadError(f"unexpected PDF Content-Type: {content_type}")
        if not body.startswith(b"%PDF-"):
            raise DownloadError("response does not have a PDF file signature")
    elif content_type not in {"text/plain", "application/octet-stream"}:
        raise DownloadError(f"unexpected text Content-Type: {content_type}")

    digest = hashlib.sha256(body).hexdigest()
    receipt = DownloadReceipt(
        source_id=source.source_id,
        filename=source.filename,
        url=source.url,
        official_landing_url=source.official_landing_url,
        downloaded_at=datetime.now(UTC).isoformat(),
        byte_count=len(body),
        sha256=digest,
        content_type=content_type,
    )
    # Write the payload first; every individual artifact is atomic. A later run
    # can safely repair missing sidecars with explicit --overwrite.
    _atomic_write(destination, body, overwrite=overwrite)
    _atomic_write(
        checksum_path,
        f"{digest}  {source.filename}\n".encode("ascii"),
        overwrite=overwrite,
    )
    receipt_bytes = (
        json.dumps(asdict(receipt), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write(receipt_path, receipt_bytes, overwrite=overwrite)
    return receipt
