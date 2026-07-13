"""In-memory image validation with lazy Pillow loading."""

from __future__ import annotations

import importlib
import warnings
from io import BytesIO
from pathlib import Path

from .integrity import reject_unsafe_path
from .models import ImageFormat, OCRConfig, OCRError, OCRErrorCode

_SUFFIX_FORMATS = {
    ".png": ImageFormat.PNG,
    ".jpg": ImageFormat.JPEG,
    ".jpeg": ImageFormat.JPEG,
}


def load_and_inspect_image(path: Path, config: OCRConfig) -> tuple[bytes, int, int, ImageFormat]:
    supplied = Path(path)
    reject_unsafe_path(supplied, field="image_path")
    try:
        resolved = supplied.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise OCRError(
            OCRErrorCode.IMAGE_NOT_FOUND,
            "image file does not exist or cannot be accessed",
            field="image_path",
        ) from exc
    if not resolved.is_file():
        raise OCRError(
            OCRErrorCode.IMAGE_NOT_FOUND,
            "image_path must identify a regular file",
            field="image_path",
        )
    try:
        with resolved.open("rb") as stream:
            data = stream.read(config.max_image_bytes + 1)
    except OSError as exc:
        raise OCRError(OCRErrorCode.INVALID_IMAGE, "could not read image") from exc
    return inspect_image_bytes(data, supplied.name, config)


def inspect_image_bytes(
    data: bytes,
    filename: str,
    config: OCRConfig,
) -> tuple[bytes, int, int, ImageFormat]:
    """Validate immutable upload bytes without creating a temporary file."""

    if type(data) is not bytes:  # noqa: E721 - mutable bytearray is intentionally rejected
        raise OCRError(OCRErrorCode.INVALID_REQUEST, "image data must be immutable bytes")
    if not isinstance(filename, str) or not filename.strip() or Path(filename).name != filename:
        raise OCRError(
            OCRErrorCode.INVALID_REQUEST,
            "filename must be a safe basename",
            field="filename",
        )
    expected_format = _SUFFIX_FORMATS.get(Path(filename).suffix.lower())
    if expected_format is None:
        raise OCRError(
            OCRErrorCode.UNSUPPORTED_FORMAT,
            "only PNG and JPEG images are accepted",
            field="filename",
        )
    if not data:
        raise OCRError(OCRErrorCode.INVALID_IMAGE, "image is empty")
    if len(data) > config.max_image_bytes:
        raise OCRError(
            OCRErrorCode.IMAGE_LIMIT_EXCEEDED,
            f"image exceeds the {config.max_image_bytes}-byte limit",
            field="image",
        )
    return _inspect_with_pillow(data, expected_format, config.max_image_pixels)


def _inspect_with_pillow(
    data: bytes,
    expected_format: ImageFormat,
    max_pixels: int,
) -> tuple[bytes, int, int, ImageFormat]:
    try:
        image_module = importlib.import_module("PIL.Image")
        pil_module = importlib.import_module("PIL")
    except (ImportError, OSError) as exc:
        raise OCRError(
            OCRErrorCode.PILLOW_UNAVAILABLE,
            "Pillow is not installed; install the project's ocr extra",
        ) from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", image_module.DecompressionBombWarning)
            with image_module.open(BytesIO(data)) as image:
                decoded_format = str(image.format or "").upper()
                width, height = (int(value) for value in image.size)
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise OCRError(
                        OCRErrorCode.IMAGE_LIMIT_EXCEEDED,
                        f"image exceeds the {max_pixels}-pixel limit",
                        field="image_path",
                    )
                actual_format = ImageFormat.PNG if decoded_format == "PNG" else ImageFormat.JPEG
                if decoded_format not in {"PNG", "JPEG"} or actual_format is not expected_format:
                    raise OCRError(
                        OCRErrorCode.UNSUPPORTED_FORMAT,
                        "image contents do not match the PNG/JPEG filename",
                        field="image_path",
                    )
                image.load()
    except OCRError:
        raise
    except (pil_module.UnidentifiedImageError, image_module.DecompressionBombError) as exc:
        raise OCRError(OCRErrorCode.INVALID_IMAGE, "invalid or unsafe image") from exc
    except image_module.DecompressionBombWarning as exc:
        raise OCRError(
            OCRErrorCode.IMAGE_LIMIT_EXCEEDED, "unsafe decompression bomb image"
        ) from exc
    except (OSError, SyntaxError, ValueError) as exc:
        raise OCRError(OCRErrorCode.INVALID_IMAGE, "invalid or truncated image") from exc
    return data, width, height, actual_format
