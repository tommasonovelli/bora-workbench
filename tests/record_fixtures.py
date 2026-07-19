"""Synthetic calibration/v3 paired evidence builders shared by record and reuse tests."""

from __future__ import annotations

from dataclasses import replace

from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_v3_types import (
    SELECTION_CPU_BASELINE,
    SELECTION_DOMINANCE,
    FinalistEvidence,
    ModeCalibration,
    ProbeRecord,
    TrialEvidence,
    TrialOrder,
)
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import TokenRate
from tests.test_calibration import cpu_target

RUN_ID = "a" * 32
_START = "2026-07-18T10:00:00Z"
_END = "2026-07-18T10:01:00Z"


def cuda_hardware() -> HardwareInfo:
    """Build deterministic CUDA hardware identity used by record fixtures."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cuda", 1, 0, "Test GPU", 8, 7)


def cpu_hardware() -> HardwareInfo:
    """Build deterministic CPU hardware identity used by record fixtures."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cpu", 0, None, None, None, None)


def record_target(hardware: HardwareInfo, mode_ids: tuple[str, ...] = ("coding",)):
    """Build a calibration target whose identity matches fixture hardware."""
    return replace(cpu_target(mode_ids), hardware=hardware)


def benchmark(rate: float) -> BenchmarkResult:
    """Build one complete benchmark result with a constant measured rate."""
    values = (rate, rate, rate, rate, rate)
    return BenchmarkResult(rate, values, TokenRate(rate, rate, rate))


def _session(
    rate: float, round_index: int, position: int, vram: VramSummary | None
) -> TrialEvidence:
    """Build one complete paired confirmation session."""
    order = TrialOrder("confirmation", position, round_index, position)
    return TrialEvidence(
        order,
        _START,
        _END,
        benchmark(rate),
        vram,
        RamSummary(24.0, 20.0),
        None,
    )


def cuda_finalist(
    n_cpu_moe: int, rates: tuple[float, float], positions: tuple[int, int], ctx: int = 131072
) -> FinalistEvidence:
    """Build one valid CUDA finalist with paired sessions and coherent VRAM evidence."""
    peak = 7.5 - 0.05 * n_cpu_moe
    vram = VramSummary(0.5, peak, 8 - peak, 0.5, "test-driver")
    sessions = (
        _session(rates[0], 1, positions[0], vram),
        _session(rates[1], 2, positions[1], vram),
    )
    return FinalistEvidence(ctx, n_cpu_moe, "valid", None, sessions, vram, RamSummary(24.0, 20.0))


def _probe() -> ProbeRecord:
    """Build one feasible screening probe with reduced process evidence."""
    vram = VramSummary(0.5, 5.6, 2.4, 0.5, "test-driver")
    trial = TrialEvidence(
        TrialOrder("screening", 1), _START, _END, None, vram, RamSummary(24.0, 20.0), None
    )
    return ProbeRecord(131072, 38, True, None, trial)


def cuda_calibration(mode) -> ModeCalibration:
    """Build one unanimously dominance-selected CUDA calibration."""
    finalists = (
        cuda_finalist(38, (62.0, 62.0), (1, 4)),
        cuda_finalist(39, (61.0, 61.0), (2, 3)),
    )
    return ModeCalibration(
        mode,
        131072,
        None,
        (_probe(),),
        False,
        finalists,
        finalists[0],
        SELECTION_DOMINANCE,
        (0, 0),
        0.0,
    )


def cpu_calibration(mode) -> ModeCalibration:
    """Build one twice-confirmed CPU baseline calibration."""
    sessions = (
        _session(9.0, 1, 1, None),
        _session(9.0, 2, 2, None),
    )
    finalist = FinalistEvidence(8192, None, "valid", None, sessions, None, RamSummary(24.0, 20.0))
    return ModeCalibration(
        mode,
        8192,
        None,
        (),
        False,
        (finalist,),
        finalist,
        SELECTION_CPU_BASELINE,
        (None, None),
        None,
    )
