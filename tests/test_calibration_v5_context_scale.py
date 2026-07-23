"""Verify calibration/v5 automatic and fixed context-scale behavior."""

from __future__ import annotations

import pytest

from qwen_launcher._calibration_v5_runner import run_calibration_v5
from qwen_launcher._calibration_v5_types import V5RunOptions
from qwen_launcher.calibration import CalibrationError
from tests.test_calibration_v5_runner import (
    active_record,
    cuda_target,
    fake_trial,
    install_fakes,
)

_CONTEXT_SCALE = [131072, 98304, 65536, 49152, 32768, 16384, 8192]


def test_automatic_search_descends_through_96k_and_48k(tmp_path, monkeypatch) -> None:
    """Probe both added rungs before selecting 48K as the first feasible context."""

    def is_feasible(spec) -> bool:
        """Make 48K the first feasible context and retain the measured MoE boundary."""
        return spec.plan.ctx <= 49152 and (spec.plan.n_cpu_moe or 0) >= 38

    install_fakes(monkeypatch, fake_trial(is_feasible))
    run_calibration_v5(cuda_target(), destination_root=tmp_path)

    record = active_record(tmp_path)
    assert record["envelope"]["ctx"] == 49152
    assert [probe["ctx"] for probe in record["search"]["probes"][:4]] == _CONTEXT_SCALE[:4]


def test_full_scale_and_axis_fit_inside_fourteen_probe_cap(tmp_path, monkeypatch) -> None:
    """Complete the worst-case seven-rung descent and 42-value boundary search."""
    install_fakes(monkeypatch, fake_trial(lambda spec: spec.plan.ctx <= 8192))

    run_calibration_v5(cuda_target(), destination_root=tmp_path)

    record = active_record(tmp_path)
    assert record["envelope"] == {"ctx": 8192, "n_cpu_moe": 0}
    assert len(record["search"]["probes"]) == 14


def test_fixed_target_uses_one_approved_automatic_rung(tmp_path, monkeypatch) -> None:
    """Keep 48K fixed while recording the complete automatic scale for reconstruction."""
    install_fakes(monkeypatch, fake_trial(lambda spec: True))
    run_calibration_v5(cuda_target(), V5RunOptions(target_ctx=49152), destination_root=tmp_path)

    record = active_record(tmp_path)
    assert record["envelope"]["ctx"] == record["search"]["target_ctx"] == 49152
    assert record["search"]["context_scale"] == _CONTEXT_SCALE


def test_infeasible_fixed_context_fails_without_descending(tmp_path, monkeypatch) -> None:
    """Keep fixed-target failure separate from automatic descent."""
    install_fakes(monkeypatch, fake_trial(lambda spec: False))

    with pytest.raises(CalibrationError, match="requested context"):
        run_calibration_v5(
            cuda_target(), V5RunOptions(target_ctx=131072), destination_root=tmp_path
        )
