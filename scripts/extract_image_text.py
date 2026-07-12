"""Run bounded local Tesseract OCR and emit non-persistent JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ocr import (  # noqa: E402
    DEFAULT_TESSERACT_PATH,
    OCRConfig,
    OCRError,
    OCRErrorCode,
    OCRErrorDetail,
    OCRLanguage,
    extract_image_text,
)


class CLIUsageError(ValueError):
    pass


class StructuredArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CLIUsageError(message)


def emit_json(payload: object) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(rendered)
    else:
        buffer.write(rendered.encode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = StructuredArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument(
        "--language",
        choices=[item.value for item in OCRLanguage],
        default=OCRLanguage.ENGLISH_HINDI.value,
    )
    parser.add_argument("--tesseract-path", type=Path, default=DEFAULT_TESSERACT_PATH)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser


def run(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        config = OCRConfig(
            tessdata_dir=args.tessdata_dir,
            language=OCRLanguage(args.language),
            tesseract_path=args.tesseract_path,
            timeout_seconds=args.timeout_seconds,
        )
        result = extract_image_text(args.image, config)
    except CLIUsageError as exc:
        return _emit_error(
            OCRErrorDetail(code=OCRErrorCode.INVALID_REQUEST, message=str(exc)),
            exit_code=2,
        )
    except ValidationError as exc:
        return _emit_error(
            OCRErrorDetail(
                code=OCRErrorCode.INVALID_REQUEST,
                message="invalid OCR configuration",
                field=str(exc.errors()[0].get("loc", ["configuration"])[0]),
            ),
            exit_code=2,
        )
    except OCRError as exc:
        runtime_codes = {
            OCRErrorCode.PILLOW_UNAVAILABLE,
            OCRErrorCode.TESSERACT_UNAVAILABLE,
            OCRErrorCode.TESSERACT_VERSION_MISMATCH,
            OCRErrorCode.OCR_TIMEOUT,
            OCRErrorCode.OCR_FAILED,
            OCRErrorCode.OUTPUT_LIMIT_EXCEEDED,
        }
        return _emit_error(exc.detail, exit_code=3 if exc.detail.code in runtime_codes else 2)
    except Exception:
        return _emit_error(
            OCRErrorDetail(
                code=OCRErrorCode.INTERNAL_ERROR,
                message="unexpected local OCR error",
            ),
            exit_code=4,
        )
    emit_json({"ok": True, "result": result.model_dump(mode="json")})
    return 0


def _emit_error(detail: OCRErrorDetail, *, exit_code: int) -> int:
    emit_json({"ok": False, "error": detail.model_dump(mode="json")})
    return exit_code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
