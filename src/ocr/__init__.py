"""Local OCR fallback with pinned model integrity and no request persistence."""

from .engine import extract_image_text
from .integrity import TESSDATA_FILES, resolve_tesseract, verify_tessdata
from .models import (
    DEFAULT_TESSERACT_PATH,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS,
    MAX_OUTPUT_BYTES,
    TESSDATA_REVISION,
    ImageFormat,
    OCRConfig,
    OCRError,
    OCRErrorCode,
    OCRErrorDetail,
    OCRLanguage,
    OCRResult,
)

__all__ = [
    "DEFAULT_TESSERACT_PATH",
    "MAX_IMAGE_BYTES",
    "MAX_IMAGE_PIXELS",
    "MAX_OUTPUT_BYTES",
    "TESSDATA_FILES",
    "TESSDATA_REVISION",
    "ImageFormat",
    "OCRConfig",
    "OCRError",
    "OCRErrorCode",
    "OCRErrorDetail",
    "OCRLanguage",
    "OCRResult",
    "extract_image_text",
    "resolve_tesseract",
    "verify_tessdata",
]
