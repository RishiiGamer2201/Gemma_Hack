"""Offline audio intake with strict privacy and resource bounds."""

from .asr import BackendFactory, transcribe_audio
from .backend import ASRBackend, BackendResult, BackendSegment, FasterWhisperBackend
from .integrity import PINNED_MODEL_FILES, PINNED_MODEL_REVISION, verify_model_bundle
from .models import (
    MAX_AUDIO_BYTES,
    MAX_AUDIO_DURATION_SECONDS,
    ASRConfig,
    ASRError,
    ASRErrorCode,
    ASRErrorDetail,
    AudioFormat,
    AudioMetadata,
    LanguageHint,
    TranscriptionResult,
    TranscriptSegment,
)

__all__ = [
    "ASRBackend",
    "ASRConfig",
    "ASRError",
    "ASRErrorCode",
    "ASRErrorDetail",
    "AudioFormat",
    "AudioMetadata",
    "BackendFactory",
    "BackendResult",
    "BackendSegment",
    "FasterWhisperBackend",
    "LanguageHint",
    "MAX_AUDIO_BYTES",
    "MAX_AUDIO_DURATION_SECONDS",
    "PINNED_MODEL_FILES",
    "PINNED_MODEL_REVISION",
    "TranscriptSegment",
    "TranscriptionResult",
    "transcribe_audio",
    "verify_model_bundle",
]
