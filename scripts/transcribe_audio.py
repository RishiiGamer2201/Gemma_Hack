"""Transcribe bounded WAV/FLAC audio with an already-downloaded local model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audio import (  # noqa: E402
    ASRConfig,
    ASRError,
    ASRErrorCode,
    ASRErrorDetail,
    LanguageHint,
    transcribe_audio,
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
    parser.add_argument("--audio", type=Path, required=True, help="Local .wav or .flac file")
    parser.add_argument(
        "--model-path", type=Path, required=True, help="Existing local model folder"
    )
    parser.add_argument(
        "--model-revision",
        required=True,
        help="Pinned model revision/digest recorded in the result; never inferred remotely",
    )
    parser.add_argument(
        "--language",
        choices=[item.value for item in LanguageHint],
        default=LanguageHint.AUTO.value,
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--compute-type",
        choices=("default", "int8", "int8_float16", "int8_float32", "float16", "float32"),
        default="default",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        config = ASRConfig(
            model_path=args.model_path,
            model_revision=args.model_revision,
            device=args.device,
            compute_type=args.compute_type,
        )
        result = transcribe_audio(args.audio, config, language=LanguageHint(args.language))
    except CLIUsageError as exc:
        return _emit_error(
            ASRErrorDetail(code=ASRErrorCode.INVALID_REQUEST, message=str(exc)),
            exit_code=2,
        )
    except ValidationError as exc:
        return _emit_error(
            ASRErrorDetail(
                code=ASRErrorCode.INVALID_REQUEST,
                message="invalid ASR configuration",
                field=str(exc.errors()[0].get("loc", ["configuration"])[0]),
            ),
            exit_code=2,
        )
    except ASRError as exc:
        runtime_codes = {
            ASRErrorCode.BACKEND_UNAVAILABLE,
            ASRErrorCode.INFERENCE_FAILED,
            ASRErrorCode.OUTPUT_LIMIT_EXCEEDED,
        }
        return _emit_error(exc.detail, exit_code=3 if exc.detail.code in runtime_codes else 2)
    except Exception:
        return _emit_error(
            ASRErrorDetail(
                code=ASRErrorCode.INTERNAL_ERROR,
                message="unexpected local transcription error",
            ),
            exit_code=4,
        )
    emit_json({"ok": True, "result": result.model_dump(mode="json")})
    return 0


def _emit_error(detail: ASRErrorDetail, *, exit_code: int) -> int:
    emit_json({"ok": False, "error": detail.model_dump(mode="json")})
    return exit_code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
