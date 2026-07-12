"""Strict contracts for local, non-persistent image OCR."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARACTERS = 100_000
MAX_TIMEOUT_SECONDS = 60.0
TESSDATA_REVISION = "87416418657359cb625c412a48b6e1d6d41c29bd"
DEFAULT_TESSERACT_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


class OCRModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, use_enum_values=False)


class OCRLanguage(StrEnum):
    ENGLISH = "eng"
    HINDI = "hin"
    ENGLISH_HINDI = "eng+hin"


class ImageFormat(StrEnum):
    PNG = "png"
    JPEG = "jpeg"


class OCRErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    IMAGE_NOT_FOUND = "image_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    IMAGE_LIMIT_EXCEEDED = "image_limit_exceeded"
    INVALID_IMAGE = "invalid_image"
    PILLOW_UNAVAILABLE = "pillow_unavailable"
    TESSERACT_UNAVAILABLE = "tesseract_unavailable"
    TESSERACT_VERSION_MISMATCH = "tesseract_version_mismatch"
    TESSERACT_INTEGRITY_FAILED = "tesseract_integrity_failed"
    TESSDATA_INTEGRITY_FAILED = "tessdata_integrity_failed"
    OCR_TIMEOUT = "ocr_timeout"
    OCR_FAILED = "ocr_failed"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    INTERNAL_ERROR = "internal_error"


class OCRErrorDetail(OCRModel):
    code: OCRErrorCode
    message: Annotated[str, Field(min_length=1, max_length=500)]
    field: Annotated[str, Field(min_length=1, max_length=80)] | None = None


class OCRError(RuntimeError):
    def __init__(self, code: OCRErrorCode, message: str, *, field: str | None = None) -> None:
        self.detail = OCRErrorDetail(code=code, message=message, field=field)
        super().__init__(message)


class OCRConfig(OCRModel):
    tessdata_dir: Path
    language: OCRLanguage = OCRLanguage.ENGLISH_HINDI
    tesseract_path: Path = DEFAULT_TESSERACT_PATH
    timeout_seconds: Annotated[float, Field(gt=0, le=MAX_TIMEOUT_SECONDS)] = 30.0
    max_image_bytes: Annotated[int, Field(gt=0, le=MAX_IMAGE_BYTES)] = MAX_IMAGE_BYTES
    max_image_pixels: Annotated[int, Field(gt=0, le=MAX_IMAGE_PIXELS)] = MAX_IMAGE_PIXELS
    max_output_bytes: Annotated[int, Field(gt=0, le=MAX_OUTPUT_BYTES)] = MAX_OUTPUT_BYTES


class OCRResult(OCRModel):
    text: Annotated[str, Field(max_length=MAX_TEXT_CHARACTERS)]
    width: Annotated[int, Field(gt=0)]
    height: Annotated[int, Field(gt=0)]
    image_format: ImageFormat
    language: OCRLanguage
    mean_confidence_percent: Annotated[float, Field(ge=0, le=100)] | None = None
    engine: Literal["tesseract"] = "tesseract"
    tesseract_version: Annotated[str, Field(min_length=1, max_length=80)]
    tessdata_revision: Literal["87416418657359cb625c412a48b6e1d6d41c29bd"] = TESSDATA_REVISION
    processing_seconds: Annotated[float, Field(ge=0)]
