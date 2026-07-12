"""Resource-bounded orchestration for offline Hindi/English ASR."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from .backend import ASRBackend, BackendResult, FasterWhisperBackend
from .integrity import verify_model_bundle
from .models import (
    MAX_SEGMENTS,
    MAX_TRANSCRIPT_CHARACTERS,
    ASRConfig,
    ASRError,
    ASRErrorCode,
    LanguageHint,
    TranscriptionResult,
    TranscriptSegment,
)
from .preflight import inspect_audio

BackendFactory = Callable[[ASRConfig, Path], ASRBackend]
ModelVerifier = Callable[[Path, str], str]


def transcribe_audio(
    audio_path: Path,
    config: ASRConfig,
    *,
    language: LanguageHint = LanguageHint.AUTO,
    backend_factory: BackendFactory = FasterWhisperBackend,
    _model_verifier: ModelVerifier | None = None,
    clock: Callable[[], float] = perf_counter,
) -> TranscriptionResult:
    """Transcribe once without writing audio, transcript, cache, or request metadata."""

    if not isinstance(language, LanguageHint):
        raise ASRError(
            ASRErrorCode.INVALID_REQUEST,
            "language must be one of: auto, hi, en",
            field="language",
        )
    audio_bytes, metadata = inspect_audio(audio_path, config)
    resolved_model = _resolve_model_directory(config.model_path)
    try:
        verified_revision = (_model_verifier or verify_model_bundle)(
            resolved_model, config.model_revision
        )
        backend = backend_factory(config, resolved_model)
        started = clock()
        raw_result = backend.transcribe(BytesIO(audio_bytes), language)
        elapsed = max(0.0, clock() - started)
    except ASRError:
        raise
    except Exception as exc:
        raise ASRError(ASRErrorCode.INFERENCE_FAILED, "local transcription failed") from exc

    try:
        segments, transcript = _normalize_output(raw_result)
        return TranscriptionResult(
            transcript=transcript,
            segments=segments,
            requested_language=language,
            detected_language=raw_result.detected_language,
            language_probability=raw_result.language_probability,
            audio=metadata,
            model_revision=verified_revision,
            processing_seconds=elapsed,
        )
    except ASRError:
        raise
    except (AttributeError, TypeError, ValueError, ValidationError) as exc:
        raise ASRError(
            ASRErrorCode.INFERENCE_FAILED,
            "backend returned invalid transcription metadata",
        ) from exc


def _resolve_model_directory(model_path: Path) -> Path:
    supplied = Path(model_path)
    if supplied.is_symlink() or str(supplied).startswith("\\\\"):
        raise ASRError(
            ASRErrorCode.MODEL_NOT_FOUND,
            "model_path must be a direct local directory",
            field="model_path",
        )
    try:
        resolved = supplied.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ASRError(
            ASRErrorCode.MODEL_NOT_FOUND,
            "model_path must be an existing local directory",
            field="model_path",
        ) from exc
    if not resolved.is_dir():
        raise ASRError(
            ASRErrorCode.MODEL_NOT_FOUND,
            "model_path must be an existing local directory",
            field="model_path",
        )
    return resolved


def _normalize_output(raw: BackendResult) -> tuple[tuple[TranscriptSegment, ...], str]:
    if len(raw.segments) > MAX_SEGMENTS:
        raise ASRError(
            ASRErrorCode.OUTPUT_LIMIT_EXCEEDED,
            f"transcription returned more than {MAX_SEGMENTS} segments",
        )
    normalized: list[TranscriptSegment] = []
    total_characters = 0
    for item in raw.segments:
        text = item.text.strip()
        if not text:
            continue
        total_characters += len(text) + (1 if normalized else 0)
        if total_characters > MAX_TRANSCRIPT_CHARACTERS:
            raise ASRError(
                ASRErrorCode.OUTPUT_LIMIT_EXCEEDED,
                f"transcript exceeds {MAX_TRANSCRIPT_CHARACTERS} characters",
            )
        try:
            segment = TranscriptSegment(
                start_seconds=item.start_seconds,
                end_seconds=item.end_seconds,
                text=text,
            )
        except (TypeError, ValueError) as exc:
            raise ASRError(
                ASRErrorCode.INFERENCE_FAILED, "backend returned an invalid segment"
            ) from exc
        normalized.append(segment)
    return tuple(normalized), " ".join(segment.text for segment in normalized)
