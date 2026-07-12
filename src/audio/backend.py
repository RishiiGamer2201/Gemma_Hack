"""Lazy faster-whisper integration constrained to an existing local model directory."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from .models import (
    MAX_SEGMENTS,
    MAX_TRANSCRIPT_CHARACTERS,
    ASRConfig,
    ASRError,
    ASRErrorCode,
    LanguageHint,
)


@dataclass(frozen=True, slots=True)
class BackendSegment:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True, slots=True)
class BackendResult:
    segments: tuple[BackendSegment, ...]
    detected_language: str | None
    language_probability: float | None


class ASRBackend(Protocol):
    def transcribe(self, audio: BytesIO, language: LanguageHint) -> BackendResult: ...


class FasterWhisperBackend:
    """Load CTranslate2 weights locally; Hugging Face download fallback is disabled."""

    def __init__(self, config: ASRConfig, model_path: Path) -> None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            module = importlib.import_module("faster_whisper")
        except (ImportError, OSError) as exc:
            raise ASRError(
                ASRErrorCode.BACKEND_UNAVAILABLE,
                "faster-whisper is not installed; install the project's speech extra",
            ) from exc
        try:
            self._model = module.WhisperModel(
                str(model_path),
                device=config.device,
                compute_type=config.compute_type,
                local_files_only=True,
            )
        except Exception as exc:
            raise ASRError(
                ASRErrorCode.BACKEND_UNAVAILABLE,
                "failed to load the local faster-whisper model",
            ) from exc

    def transcribe(self, audio: BytesIO, language: LanguageHint) -> BackendResult:
        language_code = None if language is LanguageHint.AUTO else language.value
        try:
            raw_segments, info = self._model.transcribe(
                audio,
                language=language_code,
                beam_size=5,
                temperature=0.0,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            segments: list[BackendSegment] = []
            total_characters = 0
            for segment in raw_segments:
                if len(segments) >= MAX_SEGMENTS:
                    raise ASRError(
                        ASRErrorCode.OUTPUT_LIMIT_EXCEEDED,
                        f"transcription returned more than {MAX_SEGMENTS} segments",
                    )
                text = str(segment.text)
                total_characters += len(text)
                if total_characters > MAX_TRANSCRIPT_CHARACTERS:
                    raise ASRError(
                        ASRErrorCode.OUTPUT_LIMIT_EXCEEDED,
                        f"transcript exceeds {MAX_TRANSCRIPT_CHARACTERS} characters",
                    )
                segments.append(
                    BackendSegment(
                        start_seconds=float(segment.start),
                        end_seconds=float(segment.end),
                        text=text,
                    )
                )
        except ASRError:
            raise
        except Exception as exc:
            raise ASRError(ASRErrorCode.INFERENCE_FAILED, "local transcription failed") from exc
        raw_language = getattr(info, "language", None)
        raw_probability = getattr(info, "language_probability", None)
        return BackendResult(
            segments=tuple(segments),
            detected_language=str(raw_language) if raw_language else None,
            language_probability=(float(raw_probability) if raw_probability is not None else None),
        )
