"""Offline Tesseract orchestration using in-memory image input and bounded output."""

from __future__ import annotations

import csv
import os
import re
import subprocess
import threading
from io import StringIO
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from .image import load_and_inspect_image
from .integrity import resolve_tesseract, verify_tessdata
from .models import (
    MAX_TEXT_CHARACTERS,
    OCRConfig,
    OCRError,
    OCRErrorCode,
    OCRResult,
)

_TSV_FIELDS = {
    "level",
    "page_num",
    "block_num",
    "par_num",
    "line_num",
    "word_num",
    "conf",
    "text",
}


def extract_image_text(
    image_path: Path,
    config: OCRConfig,
    *,
    clock=perf_counter,
) -> OCRResult:
    """Extract text without writing the supplied image or recognized text to disk."""

    started = clock()
    image_bytes, width, height, image_format = load_and_inspect_image(image_path, config)
    executable = resolve_tesseract(config.tesseract_path)
    tessdata_dir = verify_tessdata(config.tessdata_dir)
    version = _verify_tesseract_version(executable, config)
    raw_tsv = _run_tesseract(executable, tessdata_dir, image_bytes, config)
    text, confidence = _parse_tsv(raw_tsv)
    elapsed = max(0.0, clock() - started)
    try:
        return OCRResult(
            text=text,
            width=width,
            height=height,
            image_format=image_format,
            language=config.language,
            mean_confidence_percent=confidence,
            tesseract_version=version,
            processing_seconds=elapsed,
        )
    except ValidationError as exc:
        raise OCRError(OCRErrorCode.OCR_FAILED, "OCR returned invalid metadata") from exc


def _verify_tesseract_version(executable: Path, config: OCRConfig) -> str:
    try:
        completed = _run_bounded_process(
            [str(executable), "--version"],
            input_bytes=None,
            timeout=min(5.0, config.timeout_seconds),
            max_output_bytes=config.max_output_bytes,
        )
    except subprocess.TimeoutExpired as exc:
        raise OCRError(
            OCRErrorCode.TESSERACT_UNAVAILABLE, "Tesseract version check timed out"
        ) from exc
    except OSError as exc:
        raise OCRError(
            OCRErrorCode.TESSERACT_UNAVAILABLE, "Tesseract could not be started"
        ) from exc
    if completed.returncode != 0:
        raise OCRError(OCRErrorCode.TESSERACT_UNAVAILABLE, "Tesseract version check failed")
    output = _bounded_decode(completed.stdout, config.max_output_bytes, context="version")
    first_line = output.splitlines()[0] if output.splitlines() else ""
    match = re.fullmatch(r"tesseract\s+v?([^\s]+)", first_line.strip(), re.IGNORECASE)
    if match is None or not match.group(1).startswith("5.4.0"):
        raise OCRError(
            OCRErrorCode.TESSERACT_VERSION_MISMATCH,
            "Tesseract 5.4.0 is required",
            field="tesseract_path",
        )
    return match.group(1)


def _run_tesseract(
    executable: Path,
    tessdata_dir: Path,
    image_bytes: bytes,
    config: OCRConfig,
) -> str:
    command = [
        str(executable),
        "stdin",
        "stdout",
        "--tessdata-dir",
        str(tessdata_dir),
        "-l",
        config.language.value,
        "--psm",
        "6",
        "tsv",
    ]
    environment = os.environ.copy()
    environment["TESSDATA_PREFIX"] = str(tessdata_dir)
    try:
        completed = _run_bounded_process(
            command,
            input_bytes=image_bytes,
            timeout=config.timeout_seconds,
            max_output_bytes=config.max_output_bytes,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise OCRError(OCRErrorCode.OCR_TIMEOUT, "local OCR exceeded its time limit") from exc
    except OSError as exc:
        raise OCRError(OCRErrorCode.OCR_FAILED, "local OCR could not be started") from exc
    if completed.returncode != 0:
        raise OCRError(OCRErrorCode.OCR_FAILED, "local OCR failed")
    return _bounded_decode(completed.stdout, config.max_output_bytes, context="OCR")


def _run_bounded_process(
    command: list[str],
    *,
    input_bytes: bytes | None,
    timeout: float,
    max_output_bytes: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run without a shell while bounding both pipes before they reach memory."""

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            env=env,
        )
    except OSError as exc:
        raise OCRError(OCRErrorCode.OCR_FAILED, "local OCR could not be started") from exc

    stdout = bytearray()
    stderr = bytearray()
    overflow = threading.Event()

    def drain(pipe, target: bytearray) -> None:
        try:
            while True:
                chunk = pipe.read1(64 * 1024)
                if not chunk:
                    return
                remaining = max_output_bytes + 1 - len(target)
                target.extend(chunk[: max(0, remaining)])
                if len(target) > max_output_bytes or len(chunk) > remaining:
                    overflow.set()
                    process.kill()
                    return
        except OSError:
            return

    readers = (
        threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
    )
    for thread in readers:
        thread.start()

    def write_input() -> None:
        if process.stdin is None or input_bytes is None:
            return
        try:
            process.stdin.write(input_bytes)
        except (BrokenPipeError, OSError):
            pass
        finally:
            process.stdin.close()

    writer = threading.Thread(target=write_input, daemon=True)
    writer.start()
    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    finally:
        writer.join(timeout=2)
        for thread in readers:
            thread.join(timeout=2)
    if overflow.is_set():
        raise OCRError(
            OCRErrorCode.OUTPUT_LIMIT_EXCEEDED,
            f"local OCR output exceeded the {max_output_bytes}-byte limit",
        )
    return subprocess.CompletedProcess(command, return_code, bytes(stdout), bytes(stderr))


def _bounded_decode(raw: bytes, maximum: int, *, context: str) -> str:
    if len(raw) > maximum:
        raise OCRError(
            OCRErrorCode.OUTPUT_LIMIT_EXCEEDED,
            f"{context} output exceeded the {maximum}-byte limit",
        )
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise OCRError(OCRErrorCode.OCR_FAILED, f"{context} output was not valid UTF-8") from exc


def _parse_tsv(raw_tsv: str) -> tuple[str, float | None]:
    reader = csv.DictReader(StringIO(raw_tsv), delimiter="\t")
    if reader.fieldnames is None or not _TSV_FIELDS.issubset(reader.fieldnames):
        raise OCRError(OCRErrorCode.OCR_FAILED, "Tesseract returned malformed TSV")
    lines: dict[tuple[str, str, str, str], list[str]] = {}
    confidences: list[float] = []
    try:
        for row in reader:
            word = (row.get("text") or "").strip()
            if not word:
                continue
            key = tuple(
                row.get(field) or "" for field in ("page_num", "block_num", "par_num", "line_num")
            )
            lines.setdefault(key, []).append(word)
            confidence = float(row.get("conf") or "-1")
            if 0 <= confidence <= 100:
                confidences.append(confidence)
    except (TypeError, ValueError, csv.Error) as exc:
        raise OCRError(OCRErrorCode.OCR_FAILED, "Tesseract returned malformed TSV") from exc
    text = "\n".join(" ".join(words) for words in lines.values())
    if len(text) > MAX_TEXT_CHARACTERS:
        raise OCRError(
            OCRErrorCode.OUTPUT_LIMIT_EXCEEDED,
            f"recognized text exceeds {MAX_TEXT_CHARACTERS} characters",
        )
    confidence = sum(confidences) / len(confidences) if confidences else None
    return text, confidence
