"""Verify the local artifacts, hardware, and modes one calibration run is allowed to measure."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bora_workbench._calibration_types import CalibrationError, CalibrationRunError
from bora_workbench._model_verification import VerifyProgress
from bora_workbench.config import DEFAULT_MODEL, Config, load_config
from bora_workbench.engine import (
    JsonObject,
    ModelRequest,
    load_engine_lock,
    locate,
    resolve_model,
)
from bora_workbench.hardware import HardwareInfo, detect_hardware, ensure_launch_supported
from bora_workbench.paths import data_dir, state_dir
from bora_workbench.process import status_services
from bora_workbench.profiles import Catalog, Mode, enforce_memory_gate, load_catalog

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


def service_roots() -> tuple[Path, ...]:
    """List every root a managed service can be registered in, the state root first.

    A calibration trial registers its server under the run's own runtime tree instead of the state
    root, so a run killed before it could rotate that tree leaves a live `llama-server` that
    `status` and `stop` would never see and that no command could then end (D-071).
    """
    calibration_root = data_dir() / "calibration"
    if not calibration_root.is_dir():
        return (state_dir(),)
    trials = sorted(path.parent for path in calibration_root.glob(".runtime-*/*/*/services.json"))
    return (state_dir(), *trials)


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


def prepare_target(mode_value: str, progress: VerifyProgress | None = None) -> CalibrationTarget:
    """Verify local model, engine, memory, hardware, modes, and service exclusivity.

    ``progress`` observes the model verification, which reads the artifacts in full whenever no
    receipt covers them and would otherwise run for about a minute with no output (D-076).
    """
    config = load_config()
    hardware = detect_hardware()
    enforce_memory_gate(config, hardware, force=False)
    ensure_launch_supported(hardware)
    if config.model != DEFAULT_MODEL:
        raise CalibrationRunError("calibration supports only the pinned default model")
    for root in service_roots():
        if status_services(root).services:
            raise CalibrationRunError("a managed service is running; run bora stop")
    catalog = load_catalog()
    modes = _selected_modes(mode_value, catalog)
    lock = load_engine_lock()
    vision = any(mode.services.vision for mode in modes)
    model = resolve_model(config, lock, ModelRequest(vision, progress))
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
