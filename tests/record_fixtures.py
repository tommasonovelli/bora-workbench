"""Synthetic record builders shared by the record, reuse, and profile-matching tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from bora_workbench._calibration_record import RecordContext, build_record
from bora_workbench._calibration_runner import ModeResult
from bora_workbench._calibration_types import EnvelopeResult, GateResult, Preference
from bora_workbench.calibration import CalibrationTarget
from bora_workbench.config import Config
from bora_workbench.engine import load_engine_lock
from bora_workbench.hardware import HardwareInfo
from bora_workbench.profiles import Mode, load_catalog
from tests.sample_fixtures import sample

RUN_ID = "a" * 32
DRIVER = "test-driver"

# One possible cell per preference. The recorded needs (4.0 GiB RAM, 6.0 GiB VRAM) plus the pinned
# reserves fit the fixture hardware and fall outside the reduced-headroom variants of the tests.
_CUDA_CELLS: dict[Preference, tuple[int, int | None]] = {
    "fast": (32768, 41),
    "balanced": (131072, 38),
    "max_context": (131072, 37),
}
_CPU_CELLS: dict[Preference, tuple[int, int | None]] = {
    "fast": (8192, None),
    "balanced": (8192, None),
    "max_context": (8192, None),
}


def cuda_hardware() -> HardwareInfo:
    """Build deterministic CUDA hardware identity used by record fixtures."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cuda", 1, 0, "Test GPU", 8, 7)


def cpu_hardware() -> HardwareInfo:
    """Build deterministic CPU hardware identity used by record fixtures."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cpu", 0, None, None, None, None)


def record_target(
    hardware: HardwareInfo, mode_ids: tuple[str, ...] = ("coding",)
) -> CalibrationTarget:
    """Build a calibration target whose identity matches fixture hardware."""
    catalog = load_catalog()
    modes = tuple(mode for mode in catalog.modes if mode.id in mode_ids)
    return CalibrationTarget(
        Config(),
        hardware,
        catalog,
        modes,
        load_engine_lock(),
        Path("llama-server"),
        Path("model.gguf"),
        None,
    )


def mode_result(mode: Mode, preference: Preference, cell: tuple[int, int | None]) -> ModeResult:
    """Build one selected and gated result cell for the requested mode."""
    ctx, n_cpu_moe = cell
    measured = sample(ctx, n_cpu_moe, 100.0)
    if n_cpu_moe is None:
        measured = replace(measured, vram_needed_gib=None, vram_min_free_gib=None)
    if mode.services.vision:
        measured = replace(measured, speculative="disabled")
    gate = GateResult(True, True, True if mode.services.vision else None)
    return ModeResult(mode, EnvelopeResult(preference, measured, gate), (), ())


def calibration_document(
    hardware: HardwareInfo, mode_id: str = "coding", preference: Preference = "balanced"
) -> dict[str, object]:
    """Build one coherent synthetic record document for the given backend and mode."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    cells = _CPU_CELLS if hardware.backend == "cpu" else _CUDA_CELLS
    driver = None if hardware.backend == "cpu" else DRIVER
    context = RecordContext(record_target(hardware, (mode_id,)), RUN_ID, driver)
    return build_record(context, mode_result(mode, preference, cells[preference]))
