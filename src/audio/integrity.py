"""Pinned integrity policy for the locally installed multilingual ASR model."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from .models import ASRError, ASRErrorCode

PINNED_MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
PINNED_MODEL_FILES = {
    "config.json": (2370, "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828"),
    "model.bin": (483546902, "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"),
    "tokenizer.json": (2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
    "vocabulary.txt": (459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
}


def verify_model_bundle(model_path: Path, claimed_revision: str) -> str:
    """Verify every required asset before a backend library can inspect the folder."""

    if claimed_revision.strip() != PINNED_MODEL_REVISION:
        raise ASRError(
            ASRErrorCode.MODEL_INTEGRITY_FAILED,
            "model revision does not match the approved offline ASR build",
            field="model_revision",
        )
    if model_path.is_symlink() or str(model_path).startswith("\\\\"):
        raise ASRError(
            ASRErrorCode.MODEL_INTEGRITY_FAILED,
            "model_path must be a direct local directory",
            field="model_path",
        )
    for filename, (expected_size, expected_digest) in PINNED_MODEL_FILES.items():
        path = model_path / filename
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size != expected_size:
                raise OSError("missing or invalid model asset")
            digest = _sha256(path)
        except OSError as exc:
            raise ASRError(
                ASRErrorCode.MODEL_INTEGRITY_FAILED,
                f"required model asset failed validation: {filename}",
                field="model_path",
            ) from exc
        if not hmac.compare_digest(digest, expected_digest):
            raise ASRError(
                ASRErrorCode.MODEL_INTEGRITY_FAILED,
                f"required model asset failed validation: {filename}",
                field="model_path",
            )
    return PINNED_MODEL_REVISION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
