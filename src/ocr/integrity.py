"""Pinned tessdata and local executable verification."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from .models import DEFAULT_TESSERACT_PATH, OCRError, OCRErrorCode

PINNED_TESSERACT_SIZE = 1_585_024
PINNED_TESSERACT_SHA256 = "babb405f4366b480d02cd8ff2bac8d497170f6c1711ce6f3d5d8bf0fb7fa6ed9"

TESSDATA_FILES = {
    "configs/tsv": (
        22,
        "59d079bb75d8b3d7c839a3564580cb559e362c93a9d70f234e421c0c3e767e04",
    ),
    "eng.traineddata": (
        4_113_088,
        "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2",
    ),
    "hin.traineddata": (
        1_122_751,
        "4c73ffc59d497c186b19d1e90f5d721d678ea6b2e277b719bee4e2af12271825",
    ),
    "osd.traineddata": (
        10_562_727,
        "9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff",
    ),
}


def reject_unsafe_path(path: Path, *, field: str) -> None:
    rendered = str(path)
    if rendered.startswith(("\\\\", "//")) or ".." in path.parts:
        raise OCRError(
            OCRErrorCode.INVALID_REQUEST,
            f"{field} must be a direct local path without traversal",
            field=field,
        )
    existing_ancestors = (parent for parent in path.parents if parent.exists())
    if path.is_symlink() or any(parent.is_symlink() for parent in existing_ancestors):
        raise OCRError(
            OCRErrorCode.INVALID_REQUEST,
            f"{field} must not contain a symbolic link",
            field=field,
        )


def resolve_tesseract(path: Path) -> Path:
    reject_unsafe_path(path, field="tesseract_path")
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise OCRError(
            OCRErrorCode.TESSERACT_UNAVAILABLE,
            "configured Tesseract executable is unavailable",
            field="tesseract_path",
        ) from exc
    if not resolved.is_file():
        raise OCRError(
            OCRErrorCode.TESSERACT_UNAVAILABLE,
            "configured Tesseract executable is unavailable",
            field="tesseract_path",
        )
    try:
        trusted_path = DEFAULT_TESSERACT_PATH.resolve(strict=True)
        size = resolved.stat().st_size
        digest = _sha256(resolved)
    except OSError as exc:
        raise OCRError(
            OCRErrorCode.TESSERACT_UNAVAILABLE,
            "configured Tesseract executable could not be verified",
            field="tesseract_path",
        ) from exc
    if (
        resolved != trusted_path
        or size != PINNED_TESSERACT_SIZE
        or not hmac.compare_digest(digest, PINNED_TESSERACT_SHA256)
    ):
        raise OCRError(
            OCRErrorCode.TESSERACT_INTEGRITY_FAILED,
            "configured Tesseract executable failed integrity validation",
            field="tesseract_path",
        )
    return resolved


def verify_tessdata(directory: Path) -> Path:
    reject_unsafe_path(directory, field="tessdata_dir")
    try:
        resolved = directory.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise OCRError(
            OCRErrorCode.TESSDATA_INTEGRITY_FAILED,
            "pinned tessdata directory is unavailable",
            field="tessdata_dir",
        ) from exc
    if not resolved.is_dir():
        raise OCRError(
            OCRErrorCode.TESSDATA_INTEGRITY_FAILED,
            "pinned tessdata directory is unavailable",
            field="tessdata_dir",
        )
    for filename, (expected_size, expected_hash) in TESSDATA_FILES.items():
        candidate = resolved / filename
        if candidate.is_symlink() or not candidate.is_file():
            raise _integrity_error(filename)
        try:
            size = candidate.stat().st_size
            digest = _sha256(candidate)
        except OSError as exc:
            raise _integrity_error(filename) from exc
        if size != expected_size or digest != expected_hash:
            raise _integrity_error(filename)
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _integrity_error(filename: str) -> OCRError:
    return OCRError(
        OCRErrorCode.TESSDATA_INTEGRITY_FAILED,
        f"pinned tessdata integrity check failed for {filename}",
        field="tessdata_dir",
    )
