"""Typed evidence produced by local model-feasibility probes."""

from __future__ import annotations

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

ShortText = Annotated[str, Field(min_length=1, max_length=500)]


class FeasibilityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class GpuInventory(FeasibilityModel):
    name: ShortText
    total_vram_bytes: Annotated[int, Field(ge=0)] | None = None
    free_vram_bytes: Annotated[int, Field(ge=0)] | None = None
    driver_version: ShortText | None = None


class RuntimeInventory(FeasibilityModel):
    name: ShortText
    installed: bool
    version: ShortText | None = None
    service_reachable: bool = False
    local_models: tuple[ShortText, ...] = ()


class SystemInventory(FeasibilityModel):
    collected_at: AwareDatetime
    os_name: ShortText
    os_version: ShortText
    architecture: ShortText
    cpu_name: ShortText
    physical_cores: Annotated[int, Field(ge=1)] | None = None
    logical_cores: Annotated[int, Field(ge=1)]
    total_ram_bytes: Annotated[int, Field(gt=0)]
    system_disk_total_bytes: Annotated[int, Field(gt=0)]
    system_disk_free_bytes: Annotated[int, Field(ge=0)]
    python_version: ShortText
    gpus: tuple[GpuInventory, ...] = ()
    runtimes: tuple[RuntimeInventory, ...] = ()


class ProbeResult(FeasibilityModel):
    probe_id: Annotated[str, Field(pattern=r"^[a-z0-9_]+$", max_length=80)]
    model: ShortText
    context_tokens_requested: Annotated[int, Field(ge=1)] | None = None
    prompt_eval_count: Annotated[int, Field(ge=0)] | None = None
    eval_count: Annotated[int, Field(ge=0)] | None = None
    tokens_per_second: Annotated[float, Field(ge=0)] | None = None
    total_duration_ms: Annotated[float, Field(ge=0)]
    load_duration_ms: Annotated[float, Field(ge=0)] | None = None
    peak_system_ram_delta_bytes: Annotated[int, Field(ge=0)] | None = None
    peak_gpu_used_bytes: Annotated[int, Field(ge=0)] | None = None
    passed: bool
    output_excerpt: Annotated[str, Field(max_length=1000)] = ""
    error: ShortText | None = None


class ModelBenchmark(FeasibilityModel):
    model: ShortText
    digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    size_bytes: Annotated[int, Field(gt=0)] | None = None
    quantization: ShortText | None = None
    context_length: Annotated[int, Field(gt=0)] | None = None
    probes: tuple[ProbeResult, ...]


class FeasibilityReport(FeasibilityModel):
    schema_version: Annotated[int, Field(ge=1)] = 1
    generated_at: AwareDatetime
    inventory: SystemInventory
    benchmarks: tuple[ModelBenchmark, ...] = ()
