from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from scripts.model_feasibility import (
    benchmark_exit_code,
    load_pinned_builds,
    validate_installed_build,
)
from src.agents import OllamaResponse
from src.feasibility import FeasibilityReport, collect_system_inventory, run_model_benchmark
from src.feasibility.benchmark import ProbeSpec, ResourceSampler, _probe_passed
from src.feasibility.models import ModelBenchmark, ProbeResult


class _FakeSampler:
    peak_ram_delta = 123
    peak_gpu_bytes = 456

    def __enter__(self) -> _FakeSampler:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class _FakeClient:
    def generate(self, *, prompt: str, **_: object) -> OllamaResponse:
        if not prompt:
            text = ""
        elif "JSON only" in prompt:
            text = '{"status":"ok","language":"en"}'
        elif "READY_EN" in prompt:
            text = "READY_EN"
        elif "वेतन" in prompt:
            text = "वेतन"
        elif "salary" in prompt:
            text = "salary"
        elif "MEASURED" in prompt:
            text = "MEASURED"
        elif "COMPLETE" in prompt:
            text = "COMPLETE"
        else:
            text = "A cautious non-empty workflow response."
        return OllamaResponse(
            text=text,
            model="test-model",
            done=True,
            raw={
                "eval_count": 10,
                "eval_duration": 1_000_000_000,
                "prompt_eval_count": 20,
                "load_duration": 2_000_000,
            },
        )


def test_benchmark_records_deterministic_and_sequential_probes() -> None:
    with patch("src.feasibility.benchmark.ResourceSampler", _FakeSampler):
        result = run_model_benchmark(
            _FakeClient(),
            model="test-model",
            contexts=(256,),
            metadata={
                "digest": "a" * 64,
                "size": 1234,
                "details": {"quantization_level": "Q4_K_M"},
            },
        )
    probes = {probe.probe_id: probe for probe in result.probes}
    assert {
        "english",
        "cold_start_precondition",
        "hindi",
        "hinglish",
        "structured_json",
        "throughput_1k",
        "context_256",
        "sequential_advocate",
    } == set(probes)
    assert all(probe.passed for probe in probes.values())
    assert probes["english"].tokens_per_second == 10
    assert result.digest == "a" * 64


def test_inventory_is_strictly_serializable_without_private_data() -> None:
    with (
        patch("src.feasibility.system.windows_memory", return_value=(16_000, 8_000)),
        patch("src.feasibility.system.shutil.disk_usage") as disk_usage,
        patch("src.feasibility.system._nvidia_gpus", return_value=()),
        patch("src.feasibility.system._runtime_inventory", return_value=()),
        patch("src.feasibility.system._physical_core_count", return_value=4),
    ):
        disk_usage.return_value = type("Disk", (), {"total": 20_000, "free": 10_000})()
        inventory = collect_system_inventory()
    report = FeasibilityReport(
        generated_at=datetime.now(UTC),
        inventory=inventory,
    )
    payload = report.model_dump(mode="json")
    assert payload["inventory"]["physical_cores"] == 4
    assert "username" not in str(payload).casefold()


def test_pinned_model_metadata_must_match_the_local_manifest() -> None:
    pinned = load_pinned_builds()
    model = "gemma4:e4b-it-q4_K_M"
    expected = pinned[model]
    valid = {
        "digest": expected["expected_digest"],
        "size": expected["expected_size_bytes"],
        "details": {"quantization_level": expected["quantization"]},
    }
    validate_installed_build(model, valid, pinned)
    with pytest.raises(SystemExit, match="digest mismatch"):
        validate_installed_build(model, {**valid, "digest": "0" * 64}, pinned)


def test_failed_probe_makes_benchmark_exit_nonzero() -> None:
    failed = ProbeResult(
        probe_id="english",
        model="m",
        total_duration_ms=1,
        passed=False,
        error="failed",
    )
    assert benchmark_exit_code([ModelBenchmark(model="m", probes=(failed,))]) == 1


def test_structured_and_exact_checks_reject_superficial_matches() -> None:
    json_probe = ProbeSpec("structured", "prompt", json_keys=("status", "language"))
    assert not _probe_passed('{"status":"wrong","language":null}', json_probe)
    exact_probe = ProbeSpec("exact", "prompt", expected_text="READY_EN", exact_text=True)
    assert not _probe_passed("NOT READY_EN", exact_probe)


def test_unload_failure_is_preserved_as_a_failed_precondition() -> None:
    class Client(_FakeClient):
        def generate(self, *, prompt: str, **kwargs: object) -> OllamaResponse:
            if not prompt:
                raise RuntimeError("cannot unload")
            return super().generate(prompt=prompt, **kwargs)

    with patch("src.feasibility.benchmark.ResourceSampler", _FakeSampler):
        result = run_model_benchmark(Client(), model="test-model", contexts=(256,))
    precondition = next(
        item for item in result.probes if item.probe_id == "cold_start_precondition"
    )
    assert not precondition.passed
    assert "cannot unload" in (precondition.error or "")


def test_resource_sampler_distinguishes_missing_gpu_measurement_from_zero() -> None:
    sampler = ResourceSampler()
    sampler._baseline_ram = 100
    sampler._peak_ram = 100
    with (
        patch("src.feasibility.benchmark.windows_memory", return_value=(1000, 800)),
        patch("src.feasibility.benchmark.subprocess.run", side_effect=OSError("missing")),
    ):
        sampler._sample_once()
    assert sampler.peak_ram_delta == 100
    assert sampler.peak_gpu_bytes is None
