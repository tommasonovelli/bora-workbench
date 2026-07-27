"""Synthetic builders for calibration selection, confirmation, and record tests."""

from __future__ import annotations

from bora_workbench._calibration_search import ConfirmAt, SampleAt
from bora_workbench._calibration_types import Sample
from bora_workbench.benchmark_quick import QuickBenchResult, QuickMetric, ShortBench


def confirm_from(sample_at: SampleAt) -> ConfirmAt:
    """Derive a confirmation callable that measures exactly the short series of one sample.

    A confirmation trial differs from a sample only by omitting the long request, so a fake that
    reuses the sample's own short series keeps the two consistent without a second fake.
    """

    def confirm_at(ctx: int, n_cpu_moe: int | None) -> ShortBench:
        """Return the short series the equivalent sample would have measured."""
        return sample_at(ctx, n_cpu_moe).quick.short

    return confirm_at


def short_bench(e2e_ms: float, decode_tps: float = 50.0) -> ShortBench:
    """Build a ShortBench whose median equals the requested latency and whose spread is zero."""
    metrics = tuple(
        QuickMetric("short", e2e_ms, 0.0, decode_tps, 0.0, 8, 0, None, None) for _ in range(3)
    )
    return ShortBench(metrics)  # type: ignore[arg-type]


def quick_result(
    e2e_ms: float, prefill_tps: float = 100.0, decode_tps: float = 50.0
) -> QuickBenchResult:
    """Build a QuickBenchResult whose medians equal the requested selection metrics."""
    long = QuickMetric("long", e2e_ms, prefill_tps, decode_tps, 0.0, 8000, 0, None, None)
    return QuickBenchResult(short_bench(e2e_ms, decode_tps), long)


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
