from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from scripts.extract_image_text import run
from src.ocr import (
    MAX_IMAGE_BYTES,
    OCRConfig,
    OCRError,
    OCRErrorCode,
    OCRLanguage,
    extract_image_text,
    resolve_tesseract,
    verify_tessdata,
)
from src.ocr.engine import _run_bounded_process
from src.ocr.image import load_and_inspect_image

TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tन्याय\n"
    "5\t1\t1\t1\t1\t2\t11\t0\t10\t10\t80\trights\n"
).encode()


class FakeImage:
    def __init__(
        self, *, image_format: str = "PNG", size: tuple[int, int] = (640, 480), load_error=None
    ):
        self.format = image_format
        self.size = size
        self._load_error = load_error

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def load(self) -> None:
        if self._load_error is not None:
            raise self._load_error


class DecompressionBombWarning(Warning):
    pass


class DecompressionBombError(Exception):
    pass


class UnidentifiedImageError(Exception):
    pass


def pillow_modules(*, image=None, open_error=None):
    def open_image(_stream):
        if open_error is not None:
            raise open_error
        return image or FakeImage()

    image_module = SimpleNamespace(
        open=open_image,
        DecompressionBombWarning=DecompressionBombWarning,
        DecompressionBombError=DecompressionBombError,
    )
    pil_module = SimpleNamespace(UnidentifiedImageError=UnidentifiedImageError)
    return lambda name: image_module if name == "PIL.Image" else pil_module


class OCRTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.image = self.root / "notice.png"
        self.image.write_bytes(b"bounded-image-bytes")
        self.tessdata = self.root / "tessdata"
        self.tessdata.mkdir()
        self.executable = self.root / "tesseract.exe"
        self.executable.write_bytes(b"fixture")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def config(self, **updates: object) -> OCRConfig:
        values: dict[str, object] = {
            "tessdata_dir": self.tessdata,
            "tesseract_path": self.executable,
        }
        values.update(updates)
        return OCRConfig(**values)

    def engine_patches(self, run_side_effect):
        return (
            patch("src.ocr.engine.resolve_tesseract", return_value=self.executable.resolve()),
            patch("src.ocr.engine.verify_tessdata", return_value=self.tessdata.resolve()),
            patch("src.ocr.engine._run_bounded_process", side_effect=run_side_effect),
            patch("src.ocr.image.importlib.import_module", side_effect=pillow_modules()),
        )

    def test_unicode_ocr_uses_memory_input_and_persists_nothing(self) -> None:
        version = subprocess.CompletedProcess([], 0, b"tesseract v5.4.0.20240606\n", b"")
        recognized = subprocess.CompletedProcess([], 0, TSV, b"")
        before = {item.relative_to(self.root) for item in self.root.rglob("*")}
        times = iter((4.0, 4.3))
        patches = self.engine_patches([version, recognized])
        with patches[0], patches[1], patches[2] as run_mock, patches[3]:
            result = extract_image_text(self.image, self.config(), clock=lambda: next(times))

        self.assertEqual(result.text, "न्याय rights")
        self.assertEqual(result.mean_confidence_percent, 85.0)
        self.assertEqual((result.width, result.height), (640, 480))
        self.assertEqual(result.language, OCRLanguage.ENGLISH_HINDI)
        self.assertAlmostEqual(result.processing_seconds, 0.3)
        ocr_call = run_mock.call_args_list[1]
        self.assertEqual(ocr_call.kwargs["input_bytes"], b"bounded-image-bytes")
        self.assertEqual(ocr_call.args[0][1:3], ["stdin", "stdout"])
        self.assertNotIn(str(self.image), ocr_call.args[0])
        after = {item.relative_to(self.root) for item in self.root.rglob("*")}
        self.assertEqual(after, before)

    def test_malformed_bomb_oversized_and_pixel_heavy_images_are_rejected(self) -> None:
        cases = (
            (
                pillow_modules(open_error=UnidentifiedImageError()),
                self.config(),
                OCRErrorCode.INVALID_IMAGE,
            ),
            (
                pillow_modules(image=FakeImage(load_error=DecompressionBombError())),
                self.config(),
                OCRErrorCode.INVALID_IMAGE,
            ),
            (
                pillow_modules(image=FakeImage(size=(5_000, 5_000))),
                self.config(),
                OCRErrorCode.IMAGE_LIMIT_EXCEEDED,
            ),
        )
        for modules, config, expected in cases:
            with (
                self.subTest(expected=expected),
                patch("src.ocr.image.importlib.import_module", side_effect=modules),
                self.assertRaises(OCRError) as context,
            ):
                load_and_inspect_image(self.image, config)
            self.assertEqual(context.exception.detail.code, expected)

        with self.assertRaises(OCRError) as context:
            load_and_inspect_image(self.image, self.config(max_image_bytes=2))
        self.assertEqual(context.exception.detail.code, OCRErrorCode.IMAGE_LIMIT_EXCEEDED)

    def test_extension_content_traversal_unc_and_symlink_are_rejected(self) -> None:
        jpeg_named_png = self.root / "notice.jpg"
        jpeg_named_png.write_bytes(b"fixture")
        with (
            patch(
                "src.ocr.image.importlib.import_module",
                side_effect=pillow_modules(image=FakeImage(image_format="PNG")),
            ),
            self.assertRaises(OCRError) as context,
        ):
            load_and_inspect_image(jpeg_named_png, self.config())
        self.assertEqual(context.exception.detail.code, OCRErrorCode.UNSUPPORTED_FORMAT)

        unsafe_paths = (
            self.root / "folder" / ".." / "notice.png",
            Path(r"\\server\share\notice.png"),
        )
        for unsafe in unsafe_paths:
            with self.subTest(path=unsafe), self.assertRaises(OCRError) as context:
                load_and_inspect_image(unsafe, self.config())
            self.assertEqual(context.exception.detail.code, OCRErrorCode.INVALID_REQUEST)

        with (
            patch.object(Path, "is_symlink", autospec=True, return_value=True),
            self.assertRaises(OCRError) as context,
        ):
            load_and_inspect_image(self.image, self.config())
        self.assertEqual(context.exception.detail.code, OCRErrorCode.INVALID_REQUEST)

    def test_pinned_tessdata_detects_mutation_and_missing_files(self) -> None:
        payloads = {"eng.traineddata": b"eng", "hin.traineddata": b"hin", "osd.traineddata": b"osd"}
        specifications = {
            name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in payloads.items()
        }
        for name, data in payloads.items():
            (self.tessdata / name).write_bytes(data)
        with patch("src.ocr.integrity.TESSDATA_FILES", specifications):
            self.assertEqual(verify_tessdata(self.tessdata), self.tessdata.resolve())
            (self.tessdata / "hin.traineddata").write_bytes(b"mutated")
            with self.assertRaises(OCRError) as context:
                verify_tessdata(self.tessdata)
        self.assertEqual(context.exception.detail.code, OCRErrorCode.TESSDATA_INTEGRITY_FAILED)
        self.assertNotIn("mutated", str(context.exception))

    def test_tesseract_binary_is_hash_and_path_pinned(self) -> None:
        body = self.executable.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        with (
            patch("src.ocr.integrity.DEFAULT_TESSERACT_PATH", self.executable),
            patch("src.ocr.integrity.PINNED_TESSERACT_SIZE", len(body)),
            patch("src.ocr.integrity.PINNED_TESSERACT_SHA256", digest),
        ):
            self.assertEqual(resolve_tesseract(self.executable), self.executable.resolve())
            self.executable.write_bytes(body + b"tampered")
            with self.assertRaises(OCRError) as context:
                resolve_tesseract(self.executable)
        self.assertEqual(context.exception.detail.code, OCRErrorCode.TESSERACT_INTEGRITY_FAILED)

    def test_timeout_output_cap_version_mismatch_and_failure_are_typed(self) -> None:
        version = subprocess.CompletedProcess([], 0, b"tesseract v5.4.0.20240606\n", b"")
        scenarios = (
            (
                [version, subprocess.TimeoutExpired(["tesseract"], 1)],
                self.config(),
                OCRErrorCode.OCR_TIMEOUT,
            ),
            (
                [version, subprocess.CompletedProcess([], 0, b"x" * 100, b"")],
                self.config(max_output_bytes=50),
                OCRErrorCode.OUTPUT_LIMIT_EXCEEDED,
            ),
            (
                [subprocess.CompletedProcess([], 0, b"tesseract 6.0.0\n", b"")],
                self.config(),
                OCRErrorCode.TESSERACT_VERSION_MISMATCH,
            ),
            (
                [version, subprocess.CompletedProcess([], 1, b"", b"sensitive path")],
                self.config(),
                OCRErrorCode.OCR_FAILED,
            ),
        )
        for run_effect, config, expected in scenarios:
            patches = self.engine_patches(run_effect)
            with (
                self.subTest(expected=expected),
                patches[0],
                patches[1],
                patches[2],
                patches[3],
                self.assertRaises(OCRError) as context,
            ):
                extract_image_text(self.image, config)
            self.assertEqual(context.exception.detail.code, expected)
            self.assertNotIn("sensitive", str(context.exception))

    def test_real_process_pipe_is_killed_at_output_cap(self) -> None:
        with self.assertRaises(OCRError) as context:
            _run_bounded_process(
                [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 4096)"],
                input_bytes=None,
                timeout=10,
                max_output_bytes=32,
            )
        self.assertEqual(context.exception.detail.code, OCRErrorCode.OUTPUT_LIMIT_EXCEEDED)

    def test_optional_pillow_is_lazy_and_limits_cannot_be_relaxed(self) -> None:
        with (
            patch("src.ocr.image.importlib.import_module", side_effect=ModuleNotFoundError("PIL")),
            self.assertRaises(OCRError) as context,
        ):
            load_and_inspect_image(self.image, self.config())
        self.assertEqual(context.exception.detail.code, OCRErrorCode.PILLOW_UNAVAILABLE)

        for updates in (
            {"max_image_bytes": MAX_IMAGE_BYTES + 1},
            {"max_image_pixels": 20_000_001},
            {"max_output_bytes": 2_097_153},
            {"timeout_seconds": 61},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.config(**updates)

    def test_cli_always_emits_structured_json(self) -> None:
        version = subprocess.CompletedProcess([], 0, b"tesseract v5.4.0.20240606\n", b"")
        recognized = subprocess.CompletedProcess([], 0, TSV, b"")
        patches = self.engine_patches([version, recognized])
        output = io.StringIO()
        with patches[0], patches[1], patches[2], patches[3], redirect_stdout(output):
            code = run(
                [
                    "--image",
                    str(self.image),
                    "--tessdata-dir",
                    str(self.tessdata),
                    "--tesseract-path",
                    str(self.executable),
                    "--language",
                    "hin",
                ]
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["result"]["language"], "hin")
        self.assertIn("न्याय", payload["result"]["text"])

        output = io.StringIO()
        with redirect_stdout(output):
            code = run([])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
