"""Offline tests for run-level grouping, partial results, and the searched context scale."""

from __future__ import annotations

from pathlib import Path

import pytest

import bora_workbench._calibration_run as run_module
import bora_workbench.calibration as calibration_module
from bora_workbench._calibration_run import RunOptions, _contexts, _groups, _measure, _RunSpec
from bora_workbench._calibration_trial_control import TrialProgress
from bora_workbench._calibration_types import (
    BASELINE_CTX,
    CONTEXT_SCALE,
    MEASURABLE_CONTEXT_SCALE,
    MIN_CTX_QUICK_BENCH,
    Preference,
    SearchError,
)
from tests.record_fixtures import cpu_hardware, cuda_hardware, mode_result, record_target

_ALL = ("coding", "studio", "vstudio")


def _spec(
    hardware, mode_ids: tuple[str, ...] = _ALL, preference: Preference = "balanced"
) -> _RunSpec:
    """Build a run spec whose trials are replaced by the test's own group runner."""
    target = record_target(hardware, mode_ids)
    return _RunSpec(
        target,
        Path("runtime"),
        CONTEXT_SCALE,
        "a" * 32,
        None,
        TrialProgress(),
        preference,
    )


def test_text_modes_share_one_group_and_vision_gets_its_own() -> None:
    """Keep coding and studio on one shared hardware search; vstudio cannot share it."""
    groups = _groups(_spec(cuda_hardware()).target)

    labels = [tuple(mode.id for mode in modes) for modes, _budget in groups]
    assert labels == [("coding", "studio"), ("vstudio",)]
    assert [budget for _modes, budget in groups] == [28, 20]


def test_a_vision_only_selection_creates_no_empty_text_group() -> None:
    """Never create a group with no mode in it when only vstudio was selected."""
    groups = _groups(_spec(cuda_hardware(), ("vstudio",)).target)

    assert [tuple(mode.id for mode in modes) for modes, _budget in groups] == [("vstudio",)]


def test_a_failed_group_keeps_the_modes_that_already_finished(monkeypatch) -> None:
    """Never discard hours of completed modes because a later group's boundary moved (D-067)."""
    spec = _spec(cuda_hardware())

    def fake_group(selected_spec, modes, budget):
        """Fail only the vision group after producing both text modes."""
        if modes[0].services.vision:
            raise SearchError("(65536, 36) is no longer feasible")
        return tuple((mode_result(mode, "balanced", (8192, 41)), "driver") for mode in modes)

    monkeypatch.setattr(run_module, "_run_group_for", fake_group)

    produced, failures = _measure(spec)

    assert [result.mode.id for result, _driver in produced] == ["coding", "studio"]
    assert failures == ("vstudio: (65536, 36) is no longer feasible",)


def test_every_group_failing_reports_each_reason(monkeypatch) -> None:
    """Explain every group that failed instead of only the first one."""
    spec = _spec(cuda_hardware())

    def fake_group(selected_spec, modes, budget):
        """Fail every selected group with one deterministic search reason."""
        del selected_spec, modes, budget
        raise SearchError("no feasible context step produced a usable sample")

    monkeypatch.setattr(run_module, "_run_group_for", fake_group)

    produced, failures = _measure(spec)

    assert produced == []
    assert len(failures) == 2


def test_run_invalidating_evidence_still_stops_the_whole_run(monkeypatch) -> None:
    """Keep untrustworthy evidence fatal: it says nothing measured in this run can be believed."""
    spec = _spec(cuda_hardware())

    def fake_group(selected_spec, modes, budget):
        """Invalidate the whole run with an evidence-monitor failure."""
        del selected_spec, modes, budget
        raise RuntimeError("VRAM monitor failed")

    monkeypatch.setattr(run_module, "_run_group_for", fake_group)

    with pytest.raises(RuntimeError, match="VRAM monitor"):
        _measure(spec)


def test_requested_preference_reaches_each_shared_group(monkeypatch) -> None:
    """Apply one requested rule to text and vision searches in an all-mode run."""
    observed: list[Preference] = []
    spec = _spec(cuda_hardware(), preference="max_context")

    class FakeRunner:
        """Expose the attributes group construction binds without executing them."""

        driver = "driver"
        probe = object()
        sample = object()
        gate = object()

        def __init__(self, *args) -> None:
            """Accept the real runner construction inputs without side effects."""
            del args

    def fake_run_group(provider, targets, plan):
        """Capture each group plan without starting a trial process."""
        del provider
        observed.append(plan.preference)
        return tuple(mode_result(target.mode, plan.preference, (8192, 41)) for target in targets)

    monkeypatch.setattr(run_module, "run_group", fake_run_group)
    monkeypatch.setattr(run_module, "TrialRunner", FakeRunner)

    produced, failures = _measure(spec)

    assert [result.envelope.preference for result, _driver in produced] == [
        "max_context",
        "max_context",
        "max_context",
    ]
    assert observed == ["max_context", "max_context"]
    assert failures == ()


def test_evidence_cleanup_failure_cannot_mask_keyboard_interrupt(tmp_path, monkeypatch) -> None:
    """Preserve Ctrl-C even when retaining the interrupted run's evidence also fails."""
    target = record_target(cpu_hardware())
    monkeypatch.setattr(run_module, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        run_module,
        "_measure",
        lambda spec: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        run_module,
        "preserve_evidence",
        lambda *args: (_ for _ in ()).throw(OSError("cannot preserve evidence")),
    )

    with pytest.raises(KeyboardInterrupt):
        run_module.run_calibration(target, RunOptions())


def test_searched_contexts_follow_the_backend_and_the_expert_target() -> None:
    """Search the measurable ladder on CUDA, one context on CPU, and exactly one pinned target."""
    cuda = record_target(cuda_hardware())
    cpu = record_target(cpu_hardware())

    assert _contexts(cuda, RunOptions()) == MEASURABLE_CONTEXT_SCALE
    assert _contexts(cpu, RunOptions()) == (MIN_CTX_QUICK_BENCH,)
    assert _contexts(cuda, RunOptions(target_ctx=65536)) == (65536,)
    assert _contexts(cpu, RunOptions(target_ctx=65536)) == (65536,)


def test_the_ladder_omits_steps_the_quick_bench_cannot_fit_in() -> None:
    """Never walk a step whose every trial must fail on the pinned long request (D-071)."""
    assert MEASURABLE_CONTEXT_SCALE == (131072, 98304, 65536, 49152, 32768)
    assert 16384 in CONTEXT_SCALE and 16384 not in MEASURABLE_CONTEXT_SCALE
    assert BASELINE_CTX in CONTEXT_SCALE and BASELINE_CTX not in MEASURABLE_CONTEXT_SCALE


def test_service_roots_expose_an_unrotated_trial_server(tmp_path, monkeypatch) -> None:
    """Let status and stop reach a trial server a killed run left outside the state root."""
    monkeypatch.setattr(calibration_module, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(calibration_module, "state_dir", lambda: tmp_path / "state")
    trial = tmp_path / "data" / "calibration" / ".runtime-abc" / "coding" / "c32768-n33"
    trial.mkdir(parents=True)
    (trial / "services.json").write_text('{"version": 1, "services": []}', encoding="utf-8")

    assert calibration_module.service_roots() == (tmp_path / "state", trial)


def test_service_roots_are_just_the_state_root_without_a_calibration_tree(
    tmp_path, monkeypatch
) -> None:
    """Keep status and stop working on a host that has never calibrated."""
    monkeypatch.setattr(calibration_module, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(calibration_module, "state_dir", lambda: tmp_path / "state")

    assert calibration_module.service_roots() == (tmp_path / "state",)
