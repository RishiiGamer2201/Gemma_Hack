"""Strict contracts for local, non-persistent speech transcription."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_AUDIO_DURATION_SECONDS = 10 * 60.0
MAX_TRANSCRIPT_CHARACTERS = 100_000
MAX_SEGMENTS = 4_096


class ASRModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, use_enum_values=False, allow_inf_nan=False
    )


class LanguageHint(StrEnum):
    AUTO = "auto"
    HINDI = "hi"
    ENGLISH = "en"


class AudioFormat(StrEnum):
    WAV = "wav"
    FLAC = "flac"


class ASRErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    AUDIO_NOT_FOUND = "audio_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    AUDIO_LIMIT_EXCEEDED = "audio_limit_exceeded"
    INVALID_AUDIO = "invalid_audio"
    MODEL_NOT_FOUND = "model_not_found"
    MODEL_INTEGRITY_FAILED = "model_integrity_failed"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    INFERENCE_FAILED = "inference_failed"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    INTERNAL_ERROR = "internal_error"


class ASRErrorDetail(ASRModel):
    code: ASRErrorCode
    message: Annotated[str, Field(min_length=1, max_length=500)]
    field: Annotated[str, Field(min_length=1, max_length=80)] | None = None


class ASRError(RuntimeError):
    """Expected ASR failure carrying a stable, JSON-safe public contract."""

    def __init__(self, code: ASRErrorCode, message: str, *, field: str | None = None) -> None:
        self.detail = ASRErrorDetail(code=code, message=message, field=field)
        super().__init__(message)


class ASRConfig(ASRModel):
    """Configuration that can only tighten the application-wide resource ceilings."""

    model_path: Path
    model_revision: Annotated[str, Field(min_length=1, max_length=160)]
    device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: Literal[
        "default", "int8", "int8_float16", "int8_float32", "float16", "float32"
    ] = "default"
    max_audio_bytes: Annotated[int, Field(gt=0, le=MAX_AUDIO_BYTES)] = MAX_AUDIO_BYTES
    max_duration_seconds: Annotated[float, Field(gt=0, le=MAX_AUDIO_DURATION_SECONDS)] = (
        MAX_AUDIO_DURATION_SECONDS
    )

    @model_validator(mode="after")
    def strings_must_not_be_whitespace(self) -> ASRConfig:
        if not self.model_revision.strip():
            raise ValueError("model_revision must not be blank")
        return self


class AudioMetadata(ASRModel):
    format: AudioFormat
    size_bytes: Annotated[int, Field(gt=0)]
    duration_seconds: Annotated[float, Field(gt=0)]
    sample_rate_hz: Annotated[int, Field(ge=8_000, le=192_000)]
    channels: Annotated[int, Field(ge=1, le=8)]


class TranscriptSegment(ASRModel):
    start_seconds: Annotated[float, Field(ge=0)]
    end_seconds: Annotated[float, Field(ge=0)]
    text: Annotated[str, Field(min_length=1, max_length=10_000)]

    @model_validator(mode="after")
    def end_cannot_precede_start(self) -> TranscriptSegment:
        if self.end_seconds < self.start_seconds:
            raise ValueError("segment end_seconds cannot precede start_seconds")
        return self


class TranscriptionResult(ASRModel):
    transcript: Annotated[str, Field(max_length=MAX_TRANSCRIPT_CHARACTERS)]
    segments: tuple[TranscriptSegment, ...]
    requested_language: LanguageHint
    detected_language: Annotated[str, Field(min_length=2, max_length=32)] | None = None
    language_probability: Annotated[float, Field(ge=0, le=1)] | None = None
    audio: AudioMetadata
    backend: Literal["faster-whisper"] = "faster-whisper"
    model_revision: Annotated[str, Field(min_length=1, max_length=160)]
    processing_seconds: Annotated[float, Field(ge=0)]
