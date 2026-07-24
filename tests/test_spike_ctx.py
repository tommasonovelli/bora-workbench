"""Offline tests for the D-061 cross-context spike package."""

from __future__ import annotations

import json
from collections import Counter

import pytest

from qwen_launcher._calibration_gpu_contexts import GpuContextBaseline
from qwen_launcher._calibration_ram import RamReserveError, RamSummary
from qwen_launcher._calibration_vram import VramReleaseError, VramReserveError
from qwen_launcher.benchmark import BenchmarkError
from qwen_launcher.engine import build_command
from scripts.spike_ctx.dry_run import run_dry
from scripts.spike_ctx.search import SpikeSearchError, find_boundary
from scripts.spike_ctx.trial import TrialConfig, TrialRequest, TrialRuntime, _plan
from tests.test_calibration_v5_runner import cuda_target


def test_real_plan_uses_production_builder_with_spike_fields(tmp_path) -> None:
    """Build the real coding argv without starting a model, server, or monitor."""
    target = cuda_target()
    runtime = TrialRuntime(
        tmp_path / "process", tmp_path / "responses", GpuContextBaseline(False, ())
    )
    request = TrialRequest(target, TrialConfig(65536, 30, reasoning="off"), runtime)

    plan = _plan(request)
    command = build_command(target.executable, plan, target.lock)

    assert command[command.index("-c") + 1] == "65536"
    assert command[command.index("-ncmoe") + 1] == "30"
    assert command[command.index("--reasoning") + 1] == "off"
    assert command[command.index("--spec-draft-n-max") + 1] == "2"


def test_search_finds_boundary_with_six_classified_decisions() -> None:
    """Find the known n_cpu_moe=37 edge without exceeding the written budget."""
    search = find_boundary(lambda value: None if value >= 37 else VramReserveError("reserve"))

    assert search.boundary == 37
    assert search.prudent == 41
    assert len(search.steps) <= 7
    assert {step.resource for step in search.steps if step.resource} == {"vram"}


def test_ram_fail_moves_toward_first_feasible_point_then_only_aggressive_side() -> None:
    """Handle a RAM-constrained prudent side before locating the VRAM edge."""

    def probe(value: int) -> BaseException | None:
        """Expose one feasible interval from 5 through 10."""
        if value > 10:
            return RamReserveError(RamSummary(8.0, 1.0))
        return None if value >= 5 else VramReserveError("reserve")

    search = find_boundary(probe)

    assert search.boundary == 5
    assert search.steps[0].resource == "ram"
    assert all(step.n_cpu_moe <= 20 for step in search.steps[1:])


def test_retryable_probe_runs_once_more_and_no_further() -> None:
    """Retry release instability once while preserving the binary decision budget."""
    calls: Counter[int] = Counter()

    def probe(value: int) -> BaseException | None:
        """Make the first call for every value transient and the retry feasible."""
        calls[value] += 1
        return VramReleaseError("release") if calls[value] == 1 else None

    search = find_boundary(probe)

    assert search.boundary == 0
    assert all(count == 2 for count in calls.values())


def test_persistent_retry_or_protocol_error_stops_search() -> None:
    """Reject ambiguous retry exhaustion and semantic benchmark failures."""
    with pytest.raises(SpikeSearchError, match="remained retryable"):
        find_boundary(lambda value: VramReleaseError("release"))
    with pytest.raises(SpikeSearchError, match="protocol-invalid"):
        find_boundary(lambda value: BenchmarkError("finish_reason"))


def test_dry_run_uses_fake_timings_uncached_requests_and_manifest(tmp_path) -> None:
    """Exercise the runner against the fake server with no model, GPU, or external network."""
    output = tmp_path / "dry"

    run_dry(output)

    document = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert document["schema"] == "cross-context-spike-dry-run/v1"
    assert document["search"]["boundary"] == 37
    assert len(document["quick"]["short"]) == 3
    assert document["quick"]["long"]["prompt_n"] == 8192
    assert document["quick"]["long"]["cache_n"] == 0
    assert document["quick"]["long"]["draft_n_accepted"] == 32
    assert len(tuple((output / "responses").glob("response-*.json"))) == 5
    manifest = (output / "SHA256SUMS").read_text(encoding="utf-8")
    assert "results.json" in manifest and "response-5-long.json" in manifest
