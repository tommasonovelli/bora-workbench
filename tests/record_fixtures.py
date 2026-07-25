"""Synthetic record builders shared by the record, reuse, and profile-matching tests."""

from __future__ import annotations

from pathlib import Path

from qwen_launcher._calibration_record_build import RecordContext, build_record
from qwen_launcher._calibration_runner import ModeResult
from qwen_launcher._calibration_types import EnvelopeResult, GateResult, Preference
from qwen_launcher.calibration import CalibrationTarget
from qwen_launcher.config import Config
from qwen_launcher.engine import load_engine_lock
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import Mode, load_catalog
from tests.sample_fixtures import sample

RUN_ID = "a" * 32
DRIVER = "test-driver"

# One envelope per preference. The recorded needs (4.0 GiB RAM, 6.0 GiB VRAM) plus the pinned
# reserves fit the fixture hardware and fall outside the reduced-headroom variants of the tests.
_CUDA_ENVELOPES: dict[Preference, tuple[int, int | None]] = {
    "fast": (32768, 41),
    "balanced": (131072, 38),
    "max_context": (131072, 37),
}
_CPU_ENVELOPES: dict[Preference, tuple[int, int | None]] = {
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


def mode_result(mode: Mode, envelopes: dict[Preference, tuple[int, int | None]]) -> ModeResult:
    """Build one gated three-envelope result for the requested mode."""
    gated = {
        preference: EnvelopeResult(
            preference, sample(ctx, n_cpu_moe, 100.0), GateResult(True, True, None)
        )
        for preference, (ctx, n_cpu_moe) in envelopes.items()
    }
    return ModeResult(mode, gated, (), {preference: () for preference in envelopes})


def calibration_document(
    hardware: HardwareInfo, mode_id: str = "coding", preference: Preference = "balanced"
) -> dict[str, object]:
    """Build one coherent synthetic record document for the given backend and mode."""
    mode = load_catalog().mode(mode_id)
    assert mode is not None
    envelopes = _CPU_ENVELOPES if hardware.backend == "cpu" else _CUDA_ENVELOPES
    driver = None if hardware.backend == "cpu" else DRIVER
    context = RecordContext(record_target(hardware, (mode_id,)), RUN_ID, preference, driver)
    return build_record(context, mode_result(mode, envelopes))
