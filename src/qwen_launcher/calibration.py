"""Verify the local artifacts, hardware, and modes one calibration run is allowed to measure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from qwen_launcher._calibration_errors import CalibrationError, CalibrationRunError
from qwen_launcher.config import DEFAULT_MODEL, Config, load_config
from qwen_launcher.engine import JsonObject, load_engine_lock, locate, resolve_model
from qwen_launcher.hardware import HardwareInfo, detect_hardware, ensure_launch_supported
from qwen_launcher.process import status_services
from qwen_launcher.profiles import Catalog, Mode, enforce_memory_gate, load_catalog

__all__ = [
    "Backend",
    "CalibrationError",
    "CalibrationRunError",
    "CalibrationTarget",
    "prepare_target",
    "selected_mode_ids",
]

Backend = Literal["cuda", "cpu"]


@dataclass(frozen=True, slots=True)
class CalibrationTarget:
    """Hold verified local artifacts and hardware for selected packaged modes."""

    config: Config
    hardware: HardwareInfo
    catalog: Catalog
    modes: tuple[Mode, ...]
    lock: JsonObject
    executable: Path
    model_path: Path
    mmproj_path: Path | None


def _selected_modes(mode_value: str, catalog: Catalog) -> tuple[Mode, ...]:
    """Resolve one mode or all packaged modes in deterministic catalog order."""
    if mode_value == "all":
        return catalog.modes
    mode = catalog.mode(mode_value)
    if mode is None:
        valid = ", ".join([mode.id for mode in catalog.modes] + ["all"])
        raise CalibrationError(f"unknown calibration mode {mode_value!r}; valid values: {valid}")
    return (mode,)


def selected_mode_ids(mode_value: str) -> tuple[str, ...]:
    """Resolve the selected mode identifiers without verifying any local artifact.

    Activation only moves already measured records, so it must not require the engine, the model,
    or free memory that a full measurement run does.
    """
    return tuple(mode.id for mode in _selected_modes(mode_value, load_catalog()))


def prepare_target(mode_value: str) -> CalibrationTarget:
    """Verify local model, engine, memory, hardware, modes, and service exclusivity."""
    config = load_config()
    hardware = detect_hardware()
    enforce_memory_gate(config, hardware, force=False)
    ensure_launch_supported(hardware)
    if config.model != DEFAULT_MODEL:
        raise CalibrationRunError("calibration supports only the pinned default model")
    report = status_services()
    if report.services:
        raise CalibrationRunError("a managed service is running; stop it before calibration")
    catalog = load_catalog()
    modes = _selected_modes(mode_value, catalog)
    lock = load_engine_lock()
    model = resolve_model(config, lock, require_vision=any(mode.services.vision for mode in modes))
    executable = locate(config, hardware.backend, lock)
    return CalibrationTarget(
        config,
        hardware,
        catalog,
        modes,
        lock,
        executable,
        model.model_path,
        model.mmproj_path,
    )
