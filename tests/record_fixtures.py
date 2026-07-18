"""Synthetic calibration/v2 evidence builders shared by record and reuse tests."""

from __future__ import annotations

from dataclasses import replace

from qwen_launcher._calibration_ram import RamSummary
from qwen_launcher._calibration_v2_types import (
    SELECTION_CPU_BASELINE,
    SELECTION_DOMINANCE,
    FinalistEvidence,
    ModeCalibration,
    ProbeRecord,
)
from qwen_launcher._calibration_vram import VramSummary
from qwen_launcher.benchmark import BenchmarkResult
from qwen_launcher.hardware import HardwareInfo
from qwen_launcher.profiles import TokenRate
from tests.test_calibration import cpu_target


def cuda_hardware() -> HardwareInfo:
    """Build the deterministic CUDA hardware identity used by record fixtures."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cuda", 1, 0, "Test GPU", 8, 7)


def cpu_hardware() -> HardwareInfo:
    """Build the deterministic CPU hardware identity used by record fixtures."""
    return HardwareInfo("linux", "test", "Test CPU", 12, 32, 24, "cpu", 0, None, None, None, None)


def record_target(hardware: HardwareInfo, mode_ids: tuple[str, ...] = ("coding",)):
    """Build a calibration target whose identity matches the fixture hardware."""
    return replace(cpu_target(mode_ids), hardware=hardware)


def benchmark(rate: float) -> BenchmarkResult:
    """Build one complete benchmark result with a constant measured rate."""
    values = (rate, rate, rate, rate, rate)
    return BenchmarkResult(rate, values, TokenRate(rate, rate, rate))


def cuda_finalist(n_cpu_moe: int, rate: float, ctx: int = 131072) -> FinalistEvidence:
    """Build one valid CUDA finalist with physically coherent VRAM evidence."""
    peak = 7.5 - 0.05 * n_cpu_moe
    vram = VramSummary(0.5, peak, 8 - peak, 0.5, "test-driver")
    return FinalistEvidence(
        ctx, n_cpu_moe, "valid", None, benchmark(rate), vram, RamSummary(24.0, 20.0)
    )


def cuda_calibration(mode) -> ModeCalibration:
    """Build one dominance-selected CUDA mode calibration with screening evidence."""
    finalists = (cuda_finalist(38, 62.0), cuda_finalist(39, 61.0))
    probes = (
        ProbeRecord(131072, 20, False, "OOM: CUDA out of memory", 6.5),
        ProbeRecord(131072, 38, True, None, 5.6),
    )
    return ModeCalibration(
        mode, 131072, probes, False, finalists, finalists[0], SELECTION_DOMINANCE
    )


def cpu_calibration(mode) -> ModeCalibration:
    """Build one confirmed CPU baseline calibration without a fake search."""
    finalist = FinalistEvidence(
        8192, None, "valid", None, benchmark(9.0), None, RamSummary(24.0, 20.0)
    )
    return ModeCalibration(mode, 8192, (), False, (finalist,), finalist, SELECTION_CPU_BASELINE)
