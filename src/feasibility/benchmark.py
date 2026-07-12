"""Reproducible local-only Gemma text and resource probes."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from src.agents import OllamaResponse

from .models import ModelBenchmark, ProbeResult
from .system import MIB, windows_memory


class GenerateClient(Protocol):
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: Mapping[str, Any] | None = None,
        format: str | Mapping[str, Any] | None = None,
        keep_alive: str | int | None = None,
        think: bool | None = None,
    ) -> OllamaResponse: ...


@dataclass(frozen=True, slots=True)
class ProbeSpec:
    probe_id: str
    prompt: str
    expected_text: str | None = None
    json_keys: tuple[str, ...] = ()
    context_tokens: int | None = None
    num_predict: int = 96
    exact_text: bool = False


class ResourceSampler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._baseline_ram = 0
        self._peak_ram = 0
        self._peak_gpu: int | None = None

    def __enter__(self) -> ResourceSampler:
        try:
            total, available = windows_memory()
            self._baseline_ram = total - available
            self._peak_ram = self._baseline_ram
        except (OSError, RuntimeError):
            self._baseline_ram = -1
            self._peak_ram = -1
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    @property
    def peak_ram_delta(self) -> int | None:
        if self._baseline_ram < 0 or self._peak_ram < 0:
            return None
        return max(0, self._peak_ram - self._baseline_ram)

    @property
    def peak_gpu_bytes(self) -> int | None:
        return self._peak_gpu

    def _sample(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(0.2)

    def _sample_once(self) -> None:
        try:
            total, available = windows_memory()
            used_ram = total - available
            self._peak_ram = used_ram if self._peak_ram < 0 else max(self._peak_ram, used_ram)
        except (OSError, RuntimeError):
            pass
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            used = [int(line.strip()) for line in result.stdout.splitlines() if line.strip()]
            if used:
                measured = max(used) * MIB
                self._peak_gpu = (
                    measured if self._peak_gpu is None else max(self._peak_gpu, measured)
                )
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass


def default_probes(contexts: tuple[int, ...]) -> tuple[ProbeSpec, ...]:
    base = (
        ProbeSpec(
            "english",
            "Reply with exactly READY_EN.",
            expected_text="READY_EN",
            num_predict=16,
            exact_text=True,
        ),
        ProbeSpec(
            "hindi",
            "हिंदी में एक छोटा वाक्य लिखिए जिसमें 'वेतन' शब्द हो।",
            expected_text="वेतन",
            num_predict=48,
        ),
        ProbeSpec(
            "hinglish",
            "Hinglish mein ek line likho: salary nahi mili. Include 'salary'.",
            expected_text="salary",
            num_predict=48,
        ),
        ProbeSpec(
            "structured_json",
            "Return JSON only with keys status and language; status must be ok.",
            json_keys=("status", "language"),
            num_predict=64,
        ),
        ProbeSpec(
            "throughput_1k",
            ("fact " * 900) + "\nBegin with MEASURED, then list the integers from 1 through 100.",
            expected_text="MEASURED",
            context_tokens=2048,
            num_predict=160,
        ),
    )
    context_specs = tuple(
        ProbeSpec(
            probe_id=f"context_{context}",
            prompt=("fact " * max(1, context * 3 // 4)) + "\nReply with the single word COMPLETE.",
            expected_text="COMPLETE",
            context_tokens=context,
            num_predict=16,
            exact_text=True,
        )
        for context in contexts
    )
    return (*base, *context_specs)


def run_model_benchmark(
    client: GenerateClient,
    *,
    model: str,
    contexts: tuple[int, ...] = (2048, 4096, 8192),
    metadata: Mapping[str, Any] | None = None,
    unload_models: tuple[str, ...] = (),
) -> ModelBenchmark:
    probes: list[ProbeResult] = []
    unload_started = time.perf_counter()
    try:
        for loaded_model in dict.fromkeys((*unload_models, model)):
            client.generate(
                model=loaded_model,
                prompt="",
                keep_alive=0,
                options={"num_predict": 1},
            )
        probes.append(
            ProbeResult(
                probe_id="cold_start_precondition",
                model=model,
                total_duration_ms=(time.perf_counter() - unload_started) * 1000,
                passed=True,
            )
        )
    except Exception as exc:
        probes.append(
            ProbeResult(
                probe_id="cold_start_precondition",
                model=model,
                total_duration_ms=(time.perf_counter() - unload_started) * 1000,
                passed=False,
                error=f"model unload failed: {str(exc)[:450]}",
            )
        )
    for spec in default_probes(contexts):
        started = time.perf_counter()
        sampler: ResourceSampler | None = None
        try:
            sampler = ResourceSampler()
            with sampler:
                response = client.generate(
                    model=model,
                    prompt=spec.prompt,
                    system="Follow the user's output format exactly.",
                    options={
                        "temperature": 0,
                        "num_predict": spec.num_predict,
                        "num_ctx": spec.context_tokens or 4096,
                    },
                    format="json" if spec.json_keys else None,
                    keep_alive="5m",
                    think=False,
                )
            raw = response.raw
            passed = _probe_passed(response.text, spec)
            probes.append(
                ProbeResult(
                    probe_id=spec.probe_id,
                    model=model,
                    context_tokens_requested=spec.context_tokens,
                    prompt_eval_count=_optional_int(raw.get("prompt_eval_count")),
                    eval_count=_optional_int(raw.get("eval_count")),
                    tokens_per_second=_tokens_per_second(raw),
                    total_duration_ms=(time.perf_counter() - started) * 1000,
                    load_duration_ms=_nanoseconds_to_ms(raw.get("load_duration")),
                    peak_system_ram_delta_bytes=sampler.peak_ram_delta,
                    peak_gpu_used_bytes=sampler.peak_gpu_bytes,
                    passed=passed,
                    output_excerpt=response.text[:1000],
                    error=None if passed else "probe output failed the deterministic check",
                )
            )
        except Exception as exc:
            probes.append(
                ProbeResult(
                    probe_id=spec.probe_id,
                    model=model,
                    context_tokens_requested=spec.context_tokens,
                    total_duration_ms=(time.perf_counter() - started) * 1000,
                    peak_system_ram_delta_bytes=sampler.peak_ram_delta if sampler else None,
                    peak_gpu_used_bytes=sampler.peak_gpu_bytes if sampler else None,
                    passed=False,
                    error=str(exc)[:500] or type(exc).__name__,
                )
            )
    probes.append(_run_sequential_probe(client, model))
    details = dict(metadata or {})
    model_details = details.get("details") or {}
    return ModelBenchmark(
        model=model,
        digest=details.get("digest"),
        size_bytes=details.get("size"),
        quantization=model_details.get("quantization_level"),
        context_length=model_details.get("context_length"),
        probes=tuple(probes),
    )


def _run_sequential_probe(client: GenerateClient, model: str) -> ProbeResult:
    """Exercise the planned advocate -> opponent -> rebuttal flow."""
    started = time.perf_counter()
    sampler: ResourceSampler | None = None
    outputs: list[str] = []
    try:
        sampler = ResourceSampler()
        prompts = (
            "State one cautious argument for a worker seeking unpaid wages. Two sentences.",
            "Act as the opposing party. Identify one weakness in this argument. Two sentences.",
            "Give a cautious rebuttal to the weakness. Two sentences and no outcome prediction.",
        )
        prior = ""
        with sampler:
            for prompt in prompts:
                response = client.generate(
                    model=model,
                    prompt=f"Prior exchange:\n{prior}\n\nNext task:\n{prompt}",
                    system="Do not invent statutes, deadlines, contacts, or case outcomes.",
                    options={"temperature": 0, "num_predict": 96, "num_ctx": 4096},
                    keep_alive="5m",
                    think=False,
                )
                outputs.append(response.text)
                prior += "\n" + response.text
        passed = len(outputs) == 3 and all(output.strip() for output in outputs)
        return ProbeResult(
            probe_id="sequential_advocate",
            model=model,
            context_tokens_requested=4096,
            total_duration_ms=(time.perf_counter() - started) * 1000,
            peak_system_ram_delta_bytes=sampler.peak_ram_delta,
            peak_gpu_used_bytes=sampler.peak_gpu_bytes,
            passed=passed,
            output_excerpt="\n---\n".join(outputs)[:1000],
            error=None if passed else "sequential workflow returned an empty turn",
        )
    except Exception as exc:
        return ProbeResult(
            probe_id="sequential_advocate",
            model=model,
            context_tokens_requested=4096,
            total_duration_ms=(time.perf_counter() - started) * 1000,
            peak_system_ram_delta_bytes=sampler.peak_ram_delta if sampler else None,
            peak_gpu_used_bytes=sampler.peak_gpu_bytes if sampler else None,
            passed=False,
            error=str(exc)[:500] or type(exc).__name__,
        )


def _probe_passed(text: str, spec: ProbeSpec) -> bool:
    if spec.json_keys:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return False
        return (
            isinstance(payload, dict)
            and all(key in payload for key in spec.json_keys)
            and payload.get("status") == "ok"
            and isinstance(payload.get("language"), str)
            and bool(payload["language"].strip())
        )
    if spec.expected_text is None:
        return True
    if spec.exact_text:
        return spec.expected_text.casefold() == text.strip().casefold()
    return spec.expected_text.casefold() in text.casefold()


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and value >= 0 else None


def _nanoseconds_to_ms(value: Any) -> float | None:
    return float(value) / 1_000_000 if isinstance(value, (int, float)) and value >= 0 else None


def _tokens_per_second(raw: Mapping[str, Any]) -> float | None:
    count = raw.get("eval_count")
    duration = raw.get("eval_duration")
    if (
        not isinstance(count, (int, float))
        or not isinstance(duration, (int, float))
        or duration <= 0
    ):
        return None
    return float(count) / (float(duration) / 1_000_000_000)
