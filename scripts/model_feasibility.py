"""Inventory the demo machine and optionally benchmark pinned local Gemma builds."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents import OllamaClient  # noqa: E402
from src.feasibility import (  # noqa: E402
    FeasibilityReport,
    collect_system_inventory,
    run_model_benchmark,
)
from src.feasibility.models import ModelBenchmark  # noqa: E402

PINNED_MODELS = (
    "gemma4:e4b-it-q4_K_M",
    "gemma4:e2b-it-q4_K_M",
)


def load_pinned_builds() -> dict[str, dict[str, object]]:
    payload = json.loads((ROOT / "config" / "model_builds.json").read_text(encoding="utf-8"))
    return {str(item["tag"]): item for item in payload["models"]}


def validate_installed_build(
    model: str,
    metadata: dict[str, object],
    pinned: dict[str, dict[str, object]],
) -> None:
    expected = pinned.get(model)
    if expected is None:
        return
    actual_digest = metadata.get("digest")
    if actual_digest != expected.get("expected_digest"):
        raise SystemExit(f"digest mismatch for {model}: {actual_digest}")
    actual_size = metadata.get("size")
    if actual_size != expected.get("expected_size_bytes"):
        raise SystemExit(f"size mismatch for {model}: {actual_size}")
    details = metadata.get("details")
    actual_quantization = details.get("quantization_level") if isinstance(details, dict) else None
    if actual_quantization != expected.get("quantization"):
        raise SystemExit(f"quantization mismatch for {model}: {actual_quantization}")


def benchmark_exit_code(benchmarks: list[ModelBenchmark]) -> int:
    return 0 if all(probe.passed for item in benchmarks for probe in item.probes) else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", action="store_true", help="run deterministic probes")
    parser.add_argument("--model", action="append", dest="models", help="model tag to test")
    parser.add_argument("--contexts", default="2048,4096,8192")
    parser.add_argument("--output", type=Path, help="write the JSON evidence to this path")
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    try:
        contexts = tuple(int(value.strip()) for value in args.contexts.split(",") if value.strip())
    except ValueError as exc:
        raise SystemExit("contexts must be comma-separated integers") from exc
    if not contexts or any(value < 256 for value in contexts):
        raise SystemExit("contexts must be comma-separated integers of at least 256")
    if args.timeout <= 0:
        raise SystemExit("timeout must be positive")
    inventory = collect_system_inventory()
    benchmarks = []
    if args.benchmark:
        client = OllamaClient(timeout=args.timeout)
        installed = {str(item.get("name", "")): item for item in client.list_models()}
        pinned = load_pinned_builds()
        for model in args.models or PINNED_MODELS:
            if model not in pinned:
                raise SystemExit(f"model is not in the pinned feasibility manifest: {model}")
            if model not in installed:
                raise SystemExit(f"required local model is absent: {model}")
            validate_installed_build(model, installed[model], pinned)
            benchmarks.append(
                run_model_benchmark(
                    client,
                    model=model,
                    contexts=contexts,
                    metadata=installed[model],
                    unload_models=PINNED_MODELS,
                )
            )
    report = FeasibilityReport(
        generated_at=datetime.now(UTC),
        inventory=inventory,
        benchmarks=tuple(benchmarks),
    )
    rendered = report.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        temporary.replace(args.output)
    print(rendered)
    return benchmark_exit_code(benchmarks)


if __name__ == "__main__":
    raise SystemExit(main())
