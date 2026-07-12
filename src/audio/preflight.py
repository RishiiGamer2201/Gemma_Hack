"""Bounded audio-container validation without decoding or retaining media."""

from __future__ import annotations

import importlib
import struct
from io import BytesIO
from pathlib import Path

from .models import ASRConfig, ASRError, ASRErrorCode, AudioFormat, AudioMetadata

_SUPPORTED_SUFFIXES = {".wav": AudioFormat.WAV, ".flac": AudioFormat.FLAC}


def inspect_audio(audio_path: Path, config: ASRConfig) -> tuple[bytes, AudioMetadata]:
    """Validate a local WAV/FLAC header and return only bounded metadata."""

    supplied = Path(audio_path)
    if supplied.is_symlink():
        raise ASRError(
            ASRErrorCode.INVALID_REQUEST,
            "audio_path must not be a symbolic link",
            field="audio_path",
        )
    try:
        resolved = supplied.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ASRError(
            ASRErrorCode.AUDIO_NOT_FOUND,
            "audio file does not exist or cannot be accessed",
            field="audio_path",
        ) from exc
    if not resolved.is_file():
        raise ASRError(
            ASRErrorCode.AUDIO_NOT_FOUND,
            "audio_path must identify a regular file",
            field="audio_path",
        )

    audio_format = _SUPPORTED_SUFFIXES.get(resolved.suffix.lower())
    if audio_format is None:
        raise ASRError(
            ASRErrorCode.UNSUPPORTED_FORMAT,
            "only .wav and .flac audio files are accepted",
            field="audio_path",
        )
    try:
        audio_bytes = resolved.read_bytes()
        size_bytes = len(audio_bytes)
    except OSError as exc:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "could not inspect audio file") from exc
    if size_bytes <= 0:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "audio file is empty")
    if size_bytes > config.max_audio_bytes:
        raise ASRError(
            ASRErrorCode.AUDIO_LIMIT_EXCEEDED,
            f"audio file exceeds the {config.max_audio_bytes}-byte limit",
            field="audio_path",
        )

    if audio_format is AudioFormat.WAV:
        duration, sample_rate, channels = _inspect_wav(audio_bytes)
    else:
        duration, sample_rate, channels = _inspect_flac(
            audio_bytes, max_duration_seconds=config.max_duration_seconds
        )
    if duration <= 0:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "audio duration must be greater than zero")
    if duration > config.max_duration_seconds:
        raise ASRError(
            ASRErrorCode.AUDIO_LIMIT_EXCEEDED,
            f"audio exceeds the {config.max_duration_seconds:g}-second duration limit",
            field="audio_path",
        )
    return audio_bytes, AudioMetadata(
        format=audio_format,
        size_bytes=size_bytes,
        duration_seconds=duration,
        sample_rate_hz=sample_rate,
        channels=channels,
    )


def _inspect_wav(audio_bytes: bytes) -> tuple[float, int, int]:
    try:
        with BytesIO(audio_bytes) as stream:
            header = stream.read(12)
            if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
                raise ValueError("missing RIFF/WAVE header")
            if struct.unpack("<I", header[4:8])[0] + 8 != len(audio_bytes):
                raise ValueError("inconsistent RIFF length")
            fmt: tuple[int, int, int, int, int] | None = None
            data_size: int | None = None
            while chunk_header := stream.read(8):
                if len(chunk_header) != 8:
                    raise ValueError("truncated WAV chunk header")
                chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
                if chunk_size > len(audio_bytes):
                    raise ValueError("unsafe WAV chunk length")
                body = stream.read(chunk_size)
                if len(body) != chunk_size:
                    raise ValueError("truncated WAV chunk")
                if chunk_size % 2:
                    stream.read(1)
                if chunk_id == b"fmt " and chunk_size >= 16:
                    if fmt is not None:
                        raise ValueError("duplicate WAV fmt chunk")
                    audio_format, channels, sample_rate, byte_rate, block_align, bits = (
                        struct.unpack("<HHIIHH", body[:16])
                    )
                    fmt = (audio_format, channels, sample_rate, byte_rate, block_align)
                    if audio_format not in {1, 3}:
                        raise ValueError("unsupported WAV sample encoding")
                    allowed_bits = {8, 16, 24, 32} if audio_format == 1 else {32, 64}
                    if bits not in allowed_bits:
                        raise ValueError("unsafe WAV sample width")
                elif chunk_id == b"data":
                    if data_size is not None:
                        raise ValueError("duplicate WAV data chunk")
                    data_size = chunk_size
            if fmt is None or data_size is None:
                raise ValueError("WAV is missing fmt or data")
    except (OSError, ValueError, struct.error) as exc:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "invalid WAV container") from exc
    _, channels, sample_rate, byte_rate, block_align = fmt
    if not 1 <= channels <= 8 or not 8_000 <= sample_rate <= 192_000:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "WAV channel count or sample rate is unsafe")
    bytes_per_sample = bits // 8
    expected_block_align = channels * bytes_per_sample
    expected_byte_rate = sample_rate * expected_block_align
    if (
        block_align != expected_block_align
        or byte_rate != expected_byte_rate
        or data_size % block_align
    ):
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "WAV byte alignment is invalid")
    return data_size / byte_rate, sample_rate, channels


def _inspect_flac(audio_bytes: bytes, *, max_duration_seconds: float) -> tuple[float, int, int]:
    try:
        with BytesIO(audio_bytes) as stream:
            marker = stream.read(4)
            block_header = stream.read(4)
            if marker != b"fLaC" or len(block_header) != 4:
                raise ValueError("missing FLAC marker")
            block_type = block_header[0] & 0x7F
            block_length = int.from_bytes(block_header[1:4], "big")
            if block_type != 0 or block_length != 34:
                raise ValueError("STREAMINFO must be the first FLAC metadata block")
            stream_info = stream.read(34)
            if len(stream_info) != 34:
                raise ValueError("truncated FLAC STREAMINFO")
    except (OSError, ValueError) as exc:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "invalid FLAC container") from exc

    packed = int.from_bytes(stream_info[10:18], "big")
    sample_rate = packed >> 44
    channels = ((packed >> 41) & 0x07) + 1
    total_samples = packed & ((1 << 36) - 1)
    if not 8_000 <= sample_rate <= 192_000 or not 1 <= channels <= 8:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "FLAC channel count or sample rate is unsafe")
    if total_samples == 0:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "FLAC must declare a finite duration")
    try:
        av = importlib.import_module("av")
        decoded_samples = 0
        with av.open(BytesIO(audio_bytes), mode="r") as container:
            audio_streams = [stream for stream in container.streams if stream.type == "audio"]
            if len(audio_streams) != 1:
                raise ValueError("FLAC must contain exactly one audio stream")
            for frame in container.decode(audio_streams[0]):
                decoded_samples += int(frame.samples)
                if decoded_samples > sample_rate * max_duration_seconds:
                    raise ASRError(
                        ASRErrorCode.AUDIO_LIMIT_EXCEEDED,
                        f"audio exceeds the {max_duration_seconds:g}-second duration limit",
                        field="audio_path",
                    )
    except ASRError:
        raise
    except Exception as exc:
        raise ASRError(ASRErrorCode.INVALID_AUDIO, "invalid FLAC audio frames") from exc
    if decoded_samples <= 0 or decoded_samples != total_samples:
        raise ASRError(
            ASRErrorCode.INVALID_AUDIO,
            "FLAC decoded duration does not match STREAMINFO",
        )
    return decoded_samples / sample_rate, sample_rate, channels
