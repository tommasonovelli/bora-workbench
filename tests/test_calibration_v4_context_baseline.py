"""Offline orchestration test for one immutable GPU context baseline per v4 run."""

from __future__ import annotations

import qwen_launcher._calibration_v4_runner as runner_module
from qwen_launcher._calibration_gpu_contexts import GpuContextBaseline
from qwen_launcher._calibration_v4_runner import run_calibration_v4
from tests.test_calibration_v4_runner import cuda_target, fake_trial, install_fakes


def test_all_modes_capture_one_run_scoped_gpu_baseline(tmp_path, monkeypatch) -> None:
    """Reuse one immutable population across modes instead of absorbing inter-trial contexts."""
    install_fakes(monkeypatch, fake_trial(lambda spec: (spec.plan.n_cpu_moe or 0) >= 38))
    calls: list[int] = []

    def capture(index: int) -> GpuContextBaseline:
        """Record the sole pre-run capture without accessing host hardware."""
        calls.append(index)
        return GpuContextBaseline(True, ())

    monkeypatch.setattr(runner_module, "capture_gpu_context_baseline", capture)

    run_calibration_v4(cuda_target(("coding", "studio", "vstudio")), destination_root=tmp_path)

    assert calls == [0]
