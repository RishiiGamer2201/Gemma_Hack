"""The transcribe endpoint must not persist audio and must treat output as a draft."""

from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.state import ApiState
from src.audio.asr import ASRError, ASRErrorCode
from src.config import Settings


def tone_wav(seconds: float = 1.0, rate: int = 16_000) -> bytes:
    buffer = io.BytesIO()
    writer = wave.open(buffer, "wb")
    writer.setnchannels(1)
    writer.setsampwidth(2)
    writer.setframerate(rate)
    frames = b"".join(
        struct.pack("<h", int(1000 * math.sin(2 * math.pi * 220 * frame / rate)))
        for frame in range(int(rate * seconds))
    )
    writer.writeframes(frames)
    writer.close()
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    """A client whose ASR is faked at the app boundary.

    The real backend needs the pinned 480 MB model. The endpoint's own contract --
    reject non-audio, map errors, and above all delete the temporary clip -- is
    tested here by replacing transcribe_audio with a fake that first asserts the
    temporary file the endpoint wrote actually exists at call time.
    """

    from src.api import app as app_module
    from src.audio.asr import transcribe_audio as real_transcribe
    from src.audio.models import AudioMetadata, LanguageHint, TranscriptionResult

    def fake_transcribe(audio_path, config, *, language=LanguageHint.AUTO, **kwargs):  # noqa: ANN001
        assert Path(audio_path).is_file(), "the endpoint must write the clip before ASR runs"
        return TranscriptionResult(
            transcript="salary nahi mili",
            segments=(),
            requested_language=language,
            detected_language="en",
            language_probability=0.9,
            audio=AudioMetadata(
                format="wav", size_bytes=32_044, duration_seconds=1.0,
                sample_rate_hz=16_000, channels=1,
            ),
            model_revision=config.model_revision,
            processing_seconds=0.1,
        )

    monkeypatch.setattr(app_module, "transcribe_audio", fake_transcribe)
    _ = real_transcribe  # imported to document what is being replaced

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    state = ApiState(
        settings=Settings.from_env(),
        corpus_dir=tmp_path / "sections",
        contacts_path=tmp_path / "contacts.json",
        checklists_path=Path("config/evidence_checklists.json"),
        tessdata_dir=tmp_path / "tessdata",
        tesseract_path=tmp_path / "tesseract.exe",
        asr_model_dir=model_dir,
    )
    state.load_corpus()
    return TestClient(create_app(state))


def _temp_file_count() -> int:
    import tempfile

    return len(list(Path(tempfile.gettempdir()).glob("*.wav")))


def test_a_clip_is_transcribed_and_not_left_on_disk(client: TestClient) -> None:
    before = _temp_file_count()
    response = client.post(
        "/api/transcribe",
        files={"file": ("clip.wav", tone_wav(), "audio/wav")},
        data={"language": "hi"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "salary nahi mili"
    assert body["backend"] == "faster-whisper"
    # The temporary clip must be deleted before the response returns.
    assert _temp_file_count() == before


def test_non_audio_and_bad_language_are_rejected(client: TestClient) -> None:
    image = client.post(
        "/api/transcribe",
        files={"file": ("notice.png", b"\x89PNG\r\n", "image/png")},
        data={"language": "en"},
    )
    assert image.status_code == 415

    bad_language = client.post(
        "/api/transcribe",
        files={"file": ("clip.wav", tone_wav(), "audio/wav")},
        data={"language": "fr"},
    )
    assert bad_language.status_code == 400


def test_a_missing_model_reports_service_unavailable(
    client: TestClient, monkeypatch
) -> None:
    from src.api import app as app_module

    def raise_missing(*args, **kwargs):  # noqa: ANN002, ANN003
        raise ASRError(ASRErrorCode.MODEL_NOT_FOUND, "model missing")

    monkeypatch.setattr(app_module, "transcribe_audio", raise_missing)
    response = client.post(
        "/api/transcribe",
        files={"file": ("clip.wav", tone_wav(), "audio/wav")},
        data={"language": "en"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "model_not_found"
