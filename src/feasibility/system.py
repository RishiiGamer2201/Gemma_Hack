"""Dependency-free, privacy-bounded machine and runtime inventory."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .models import GpuInventory, RuntimeInventory, SystemInventory

MIB = 1024 * 1024


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong),
        ("memory_load", ctypes.c_ulong),
        ("total_physical", ctypes.c_ulonglong),
        ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong),
        ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong),
    ]


def windows_memory() -> tuple[int, int]:
    if os.name != "nt":
        raise RuntimeError("Windows memory inventory is available only on Windows")
    status = _MemoryStatus()
    status.length = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    return int(status.total_physical), int(status.available_physical)


def run_bounded(command: Sequence[str], *, timeout: float = 10.0) -> tuple[int, str]:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    output = (result.stdout or result.stderr).strip()
    return result.returncode, output[:100_000]


def _nvidia_gpus() -> tuple[GpuInventory, ...]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return ()
    code, output = run_bounded(
        [
            executable,
            "--query-gpu=name,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if code != 0:
        return ()
    gpus: list[GpuInventory] = []
    for row in output.splitlines():
        parts = [part.strip() for part in row.split(",")]
        if len(parts) != 4:
            continue
        try:
            total = int(parts[1]) * MIB
            free = int(parts[2]) * MIB
        except ValueError:
            continue
        gpus.append(
            GpuInventory(
                name=parts[0],
                total_vram_bytes=total,
                free_vram_bytes=free,
                driver_version=parts[3],
            )
        )
    return tuple(gpus)


def ollama_executable() -> str | None:
    located = shutil.which("ollama")
    if located:
        return located
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            pass
    return None


def _runtime_inventory() -> tuple[RuntimeInventory, ...]:
    records: list[RuntimeInventory] = []
    ollama = ollama_executable()
    if ollama is None:
        records.append(RuntimeInventory(name="ollama", installed=False))
    else:
        version_code, version_output = run_bounded([ollama, "--version"], timeout=5)
        list_code, list_output = run_bounded([ollama, "list"], timeout=10)
        models = (
            tuple(columns[0] for line in list_output.splitlines()[1:] if (columns := line.split()))
            if list_code == 0
            else ()
        )
        records.append(
            RuntimeInventory(
                name="ollama",
                installed=True,
                version=version_output.splitlines()[0]
                if version_code == 0 and version_output
                else None,
                service_reachable=list_code == 0,
                local_models=models,
            )
        )
    for name in ("llama-cli", "llama-server"):
        executable = shutil.which(name)
        code, output = run_bounded([executable, "--version"]) if executable else (1, "")
        records.append(
            RuntimeInventory(
                name=name,
                installed=executable is not None,
                version=output.splitlines()[0] if code == 0 and output else None,
            )
        )
    return tuple(records)


def collect_system_inventory() -> SystemInventory:
    total_ram, _ = windows_memory() if os.name == "nt" else _posix_memory()
    disk = shutil.disk_usage(Path.cwd().anchor or "/")
    cpu = platform.processor().strip() or os.getenv("PROCESSOR_IDENTIFIER", "unknown CPU")
    return SystemInventory(
        collected_at=datetime.now(UTC),
        os_name=platform.system(),
        os_version=platform.version(),
        architecture=platform.machine() or "unknown",
        cpu_name=cpu,
        physical_cores=_physical_core_count(),
        logical_cores=os.cpu_count() or 1,
        total_ram_bytes=total_ram,
        system_disk_total_bytes=disk.total,
        system_disk_free_bytes=disk.free,
        python_version=platform.python_version(),
        gpus=_nvidia_gpus(),
        runtimes=_runtime_inventory(),
    )


def _physical_core_count() -> int | None:
    if os.name != "nt":
        return None
    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if powershell is None:
        return None
    code, output = run_bounded(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum",
        ]
    )
    if code != 0:
        return None
    try:
        value = int(output.splitlines()[-1].strip())
    except (IndexError, ValueError):
        return None
    return value if value > 0 else None


def _posix_memory() -> tuple[int, int]:
    path = Path("/proc/meminfo")
    if not path.is_file():
        raise RuntimeError("physical memory inventory is unavailable")
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        values[key] = int(raw.strip().split()[0]) * 1024
    return values["MemTotal"], values["MemAvailable"]
