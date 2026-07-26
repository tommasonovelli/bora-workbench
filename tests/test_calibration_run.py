"""Offline tests for run-level grouping, partial results, and the searched context scale."""

from __future__ import annotations

from pathlib import Path

import pytest

import bora_workbench._calibration_run as run_module
from bora_workbench._calibration_run import RunOptions, _contexts, _groups, _measure, _RunSpec
from bora_workbench._calibration_trial_control import TrialProgress
from bora_workbench._calibration_types import BASELINE_CTX, CONTEXT_SCALE, Preference, SearchError
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
    """Search the full ladder on CUDA, one baseline on CPU, and exactly one pinned target."""
    cuda = record_target(cuda_hardware())
    cpu = record_target(cpu_hardware())

    assert _contexts(cuda, RunOptions()) == CONTEXT_SCALE
    assert _contexts(cpu, RunOptions()) == (BASELINE_CTX,)
    assert _contexts(cuda, RunOptions(target_ctx=65536)) == (65536,)
    assert _contexts(cpu, RunOptions(target_ctx=65536)) == (65536,)
