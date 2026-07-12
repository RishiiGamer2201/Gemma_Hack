from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import wave
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from scripts.transcribe_audio import run
from src.audio import (
    MAX_AUDIO_BYTES,
    PINNED_MODEL_REVISION,
    ASRConfig,
    ASRError,
    ASRErrorCode,
    BackendResult,
    BackendSegment,
    FasterWhisperBackend,
    LanguageHint,
    transcribe_audio,
    verify_model_bundle,
)


def write_wav(path: Path, *, frames: int = 1_600, sample_rate: int = 16_000) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(b"\x00\x00" * frames)


def write_flac(path: Path, *, samples: int = 16_000, sample_rate: int = 16_000) -> None:
    import av

    with av.open(str(path), "w") as container:
        stream = container.add_stream("flac", rate=sample_rate)
        frame = av.AudioFrame(format="s16", layout="mono", samples=samples)
        frame.sample_rate = sample_rate
        frame.planes[0].update(bytes(frame.planes[0].buffer_size))
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)


@dataclass
class FakeBackend:
    result: BackendResult
    received_audio: bytes | None = None
    received_language: LanguageHint | None = None

    def transcribe(self, audio, language: LanguageHint) -> BackendResult:
        self.received_audio = audio.read()
        self.received_language = language
        return self.result


class AudioASRTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.audio = self.root / "request.wav"
        self.model = self.root / "whisper-ct2"
        self.model.mkdir()
        write_wav(self.audio)
        self.verifier = patch(
            "src.audio.asr.verify_model_bundle", return_value="sha256:fixture-revision"
        )
        self.verifier.start()

    def tearDown(self) -> None:
        self.verifier.stop()
        self.temporary.cleanup()

    def config(self, **updates: object) -> ASRConfig:
        values: dict[str, object] = {
            "model_path": self.model,
            "model_revision": "sha256:fixture-revision",
        }
        values.update(updates)
        return ASRConfig(**values)

    def test_mocked_backend_transcribes_hindi_without_persisting_output(self) -> None:
        raw = BackendResult(
            segments=(
                BackendSegment(0.0, 0.4, "  मेरा "),
                BackendSegment(0.4, 0.9, "वेतन नहीं मिला  "),
            ),
            detected_language="hi",
            language_probability=0.98,
        )
        backend = FakeBackend(raw)
        before = {path.relative_to(self.root) for path in self.root.rglob("*")}
        times = iter((10.0, 10.25))

        result = transcribe_audio(
            self.audio,
            self.config(),
            language=LanguageHint.HINDI,
            backend_factory=lambda _config, resolved_model: (
                backend if resolved_model == self.model.resolve() else None  # type: ignore[return-value]
            ),
            clock=lambda: next(times),
        )

        self.assertEqual(result.transcript, "मेरा वेतन नहीं मिला")
        self.assertEqual(result.requested_language, LanguageHint.HINDI)
        self.assertEqual(result.detected_language, "hi")
        self.assertEqual(result.model_revision, "sha256:fixture-revision")
        self.assertEqual(result.processing_seconds, 0.25)
        self.assertEqual(backend.received_audio, self.audio.read_bytes())
        self.assertEqual(backend.received_language, LanguageHint.HINDI)
        after = {path.relative_to(self.root) for path in self.root.rglob("*")}
        self.assertEqual(after, before)

    def test_auto_language_and_flac_header_are_supported(self) -> None:
        try:
            import av  # noqa: F401
        except ImportError:
            self.skipTest("speech extra is not installed")
        flac = self.root / "request.flac"
        write_flac(flac)
        backend = FakeBackend(BackendResult((), "en", 0.75))
        result = transcribe_audio(
            flac,
            self.config(),
            backend_factory=lambda _config, _model: backend,
        )
        self.assertEqual(result.audio.format.value, "flac")
        self.assertEqual(result.audio.duration_seconds, 1.0)
        self.assertEqual(backend.received_language, LanguageHint.AUTO)

    def test_unsupported_invalid_oversize_and_overduration_audio_are_rejected(self) -> None:
        text_file = self.root / "request.mp3"
        text_file.write_bytes(b"not an mp3")
        invalid_wav = self.root / "broken.wav"
        invalid_wav.write_bytes(b"not a wav")
        inconsistent_wav = self.root / "inconsistent.wav"
        inconsistent = bytearray(self.audio.read_bytes())
        inconsistent[28:32] = (1_000_000_000).to_bytes(4, "little")
        inconsistent_wav.write_bytes(inconsistent)
        cases = (
            (text_file, self.config(), ASRErrorCode.UNSUPPORTED_FORMAT),
            (invalid_wav, self.config(), ASRErrorCode.INVALID_AUDIO),
            (inconsistent_wav, self.config(), ASRErrorCode.INVALID_AUDIO),
            (self.audio, self.config(max_audio_bytes=10), ASRErrorCode.AUDIO_LIMIT_EXCEEDED),
            (
                self.audio,
                self.config(max_duration_seconds=0.01),
                ASRErrorCode.AUDIO_LIMIT_EXCEEDED,
            ),
        )
        for path, config, expected in cases:
            with self.subTest(expected=expected), self.assertRaises(ASRError) as context:
                transcribe_audio(
                    path,
                    config,
                    backend_factory=lambda _c, _m: FakeBackend(BackendResult((), None, None)),
                )
            self.assertEqual(context.exception.detail.code, expected)

    def test_missing_model_and_output_limits_have_typed_errors(self) -> None:
        missing = self.root / "missing-model"
        with self.assertRaises(ASRError) as context:
            transcribe_audio(self.audio, self.config(model_path=missing))
        self.assertEqual(context.exception.detail.code, ASRErrorCode.MODEL_NOT_FOUND)

        backend = FakeBackend(
            BackendResult(
                (BackendSegment(0, 1, "x" * 100_001),),
                "en",
                0.9,
            )
        )
        with self.assertRaises(ASRError) as context:
            transcribe_audio(self.audio, self.config(), backend_factory=lambda _c, _m: backend)
        self.assertEqual(context.exception.detail.code, ASRErrorCode.OUTPUT_LIMIT_EXCEEDED)

        invalid_metadata = FakeBackend(BackendResult((), "en", 1.5))
        with self.assertRaises(ASRError) as context:
            transcribe_audio(
                self.audio,
                self.config(),
                backend_factory=lambda _c, _m: invalid_metadata,
            )
        self.assertEqual(context.exception.detail.code, ASRErrorCode.INFERENCE_FAILED)

        with self.assertRaises(ASRError) as context:
            transcribe_audio(
                self.audio,
                self.config(),
                language="hi",  # type: ignore[arg-type]
                backend_factory=lambda _c, _m: invalid_metadata,
            )
        self.assertEqual(context.exception.detail.code, ASRErrorCode.INVALID_REQUEST)

    def test_configuration_cannot_relax_global_limits_or_use_blank_revision(self) -> None:
        for updates in (
            {"max_audio_bytes": MAX_AUDIO_BYTES + 1},
            {"max_duration_seconds": 601},
            {"model_revision": "   "},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.config(**updates)

    def test_model_bundle_hashes_are_verified_before_backend_construction(self) -> None:
        bundle = self.root / "verified-model"
        bundle.mkdir()
        contents = {"config.json": b"config", "model.bin": b"model", "tokenizer.json": b"token"}
        for name, body in contents.items():
            (bundle / name).write_bytes(body)
        expected = {
            name: (len(body), hashlib.sha256(body).hexdigest()) for name, body in contents.items()
        }
        with patch("src.audio.integrity.PINNED_MODEL_FILES", expected):
            self.assertEqual(
                verify_model_bundle(bundle, PINNED_MODEL_REVISION), PINNED_MODEL_REVISION
            )
            (bundle / "tokenizer.json").write_bytes(b"tampered")
            with self.assertRaises(ASRError) as context:
                verify_model_bundle(bundle, PINNED_MODEL_REVISION)
        self.assertEqual(context.exception.detail.code, ASRErrorCode.MODEL_INTEGRITY_FAILED)

        with self.assertRaises(ASRError) as context:
            verify_model_bundle(bundle, "untrusted-revision")
        self.assertEqual(context.exception.detail.code, ASRErrorCode.MODEL_INTEGRITY_FAILED)

    def test_faster_whisper_loads_local_only_and_maps_language_hint(self) -> None:
        raw_segment = SimpleNamespace(start=0.0, end=1.0, text=" salary due ")
        info = SimpleNamespace(language="en", language_probability=0.88)

        class WhisperModel:
            init_args: tuple[tuple[object, ...], dict[str, object]] | None = None
            transcribe_args: tuple[tuple[object, ...], dict[str, object]] | None = None

            def __init__(self, *args: object, **kwargs: object) -> None:
                type(self).init_args = (args, kwargs)

            def transcribe(self, *args: object, **kwargs: object) -> tuple[list[object], object]:
                type(self).transcribe_args = (args, kwargs)
                return [raw_segment], info

        with patch(
            "src.audio.backend.importlib.import_module",
            return_value=SimpleNamespace(WhisperModel=WhisperModel),
        ):
            backend = FasterWhisperBackend(
                self.config(device="cpu", compute_type="int8"), self.model
            )
            result = backend.transcribe(self.audio, LanguageHint.ENGLISH)

        assert WhisperModel.init_args is not None
        self.assertEqual(WhisperModel.init_args[0], (str(self.model),))
        self.assertEqual(
            WhisperModel.init_args[1],
            {"device": "cpu", "compute_type": "int8", "local_files_only": True},
        )
        assert WhisperModel.transcribe_args is not None
        self.assertEqual(WhisperModel.transcribe_args[1]["language"], "en")
        self.assertFalse(WhisperModel.transcribe_args[1]["condition_on_previous_text"])
        self.assertEqual(result.segments[0].text, " salary due ")

        with (
            patch(
                "src.audio.backend.importlib.import_module",
                side_effect=ModuleNotFoundError("faster_whisper"),
            ),
            self.assertRaises(ASRError) as context,
        ):
            FasterWhisperBackend(self.config(), self.model)
        self.assertEqual(context.exception.detail.code, ASRErrorCode.BACKEND_UNAVAILABLE)

    def test_cli_emits_structured_json_for_success_and_errors(self) -> None:
        result = transcribe_audio(
            self.audio,
            self.config(),
            backend_factory=lambda _c, _m: FakeBackend(BackendResult((), "en", 0.8)),
        )
        output = io.StringIO()
        with (
            patch("scripts.transcribe_audio.transcribe_audio", return_value=result),
            redirect_stdout(output),
        ):
            code = run(
                [
                    "--audio",
                    str(self.audio),
                    "--model-path",
                    str(self.model),
                    "--model-revision",
                    "sha256:fixture-revision",
                    "--language",
                    "en",
                ]
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["result"]["model_revision"], "sha256:fixture-revision")

        output = io.StringIO()
        with redirect_stdout(output):
            code = run([])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
