"""Synthetic builders for calibration selection, confirmation, and record tests."""

from __future__ import annotations

from qwen_launcher._calibration_types import Sample
from qwen_launcher.benchmark_quick import QuickBenchResult, QuickMetric


def quick_result(
    e2e_ms: float, prefill_tps: float = 100.0, decode_tps: float = 50.0
) -> QuickBenchResult:
    """Build a QuickBenchResult whose medians equal the requested selection metrics."""
    short = tuple(
        QuickMetric("short", e2e_ms, 0.0, decode_tps, 0.0, 8, 0, None, None) for _ in range(3)
    )
    long = QuickMetric("long", e2e_ms, prefill_tps, decode_tps, 0.0, 8000, 0, None, None)
    return QuickBenchResult(short, long)  # type: ignore[arg-type]


def sample(
    ctx: int,
    n_cpu_moe: int | None,
    e2e_ms: float,
    *,
    prefill_tps: float = 100.0,
    decode_tps: float = 50.0,
    vram_free: float = 1.0,
) -> Sample:
    """Build one feasible sample with controllable selection metrics."""
    return Sample(
        ctx,
        n_cpu_moe,
        "mtp2",
        quick_result(e2e_ms, prefill_tps, decode_tps),
        ram_needed_gib=4.0,
        vram_needed_gib=6.0,
        ram_min_available_gib=10.0,
        vram_min_free_gib=vram_free,
    )
