"""Build the Rich doctor table while keeping the command boundary concise."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.table import Table

from qwen_launcher.config import Config
from qwen_launcher.hardware import HardwareInfo


@dataclass(frozen=True, slots=True)
class DoctorData:
    """Group read-only doctor values and computed public paths."""

    config: Config
    hardware: HardwareInfo
    profiles: int
    version: str
    directories: tuple[Path, Path, Path, Path]


def _gib(value: float | None) -> str:
    """Format an exact GiB measurement for human diagnostics."""
    return "not applicable" if value is None else f"{value:.2f} GiB"


def _gpu_label(hardware: HardwareInfo) -> str:
    """Describe the selected GPU without implying multi-GPU launch support."""
    if hardware.gpu_index is None:
        return "none"
    return f"{hardware.gpu_name} (index {hardware.gpu_index}, detected {hardware.gpu_count})"


def build_doctor_table(data: DoctorData) -> Table:
    """Build the read-only diagnostics table from already collected service values."""
    config, hardware = data.config, data.hardware
    table = Table(title="qwen-launcher diagnostics")
    table.add_column("Item")
    table.add_column("Value")
    rows = [
        ("Version", data.version),
        ("Configuration", "valid"),
        ("Model", config.model),
        ("llama.cpp port", str(config.llama_port)),
        ("OS", f"{hardware.os_name} — {hardware.os_version}"),
        ("CPU", f"{hardware.cpu_name} ({hardware.cpu_cores} logical cores)"),
        ("RAM total", _gib(hardware.ram_total_gib)),
        ("RAM available", _gib(hardware.ram_available_gib)),
        ("Backend", hardware.backend),
        ("GPU", _gpu_label(hardware)),
        ("VRAM total", _gib(hardware.vram_total_gib)),
        ("VRAM free", _gib(hardware.vram_free_gib)),
        ("Calibrated profiles", str(data.profiles) if data.profiles else "none"),
        ("Config directory", str(data.directories[0])),
        ("Data directory", str(data.directories[1])),
        ("Cache directory", str(data.directories[2])),
        ("State directory", str(data.directories[3])),
    ]
    for label, value in rows:
        table.add_row(label, value)
    return table
