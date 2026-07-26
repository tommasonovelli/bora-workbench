"""Offline tests for calibration CLI routing, option validation, and exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from rich.console import Console

import bora_workbench._cli_calibration as calibration_cli
from bora_workbench._calibration_run import RunResult
from bora_workbench._calibration_runner import ModeResult
from bora_workbench._calibration_types import (
    CONTEXT_SCALE,
    MEASURABLE_CONTEXT_SCALE,
    EnvelopeResult,
    GateResult,
    SearchError,
    UnclassifiableTrialError,
)
from bora_workbench._cli_calibration import (
    CalibrationCliInput,
    _preference,
    _validate,
    parse_calibration_input,
    run_calibrate,
    show_outcome,
)
from bora_workbench.calibration import CalibrationError
from bora_workbench.profiles import load_catalog
from tests.sample_fixtures import sample


def _output() -> tuple[Console, Console]:
    """Return quiet CLI streams for exit-code assertions."""
    return Console(quiet=True), Console(quiet=True)


def test_preference_normalization_and_rejection() -> None:
    """Normalize max-context, default to balanced, and reject an unknown preference."""
    assert _preference("max-context") == "max_context"
    assert _preference(None) == "balanced"
    with pytest.raises(CalibrationError):
        _preference("turbo")


def test_extras_parse_activation_and_target_context() -> None:
    """Accept exactly the documented extras and reject anything else before hardware work."""
    parsed = parse_calibration_input("coding", None, ["--no-activate", "--target-ctx", "65536"])

    assert (parsed.no_activate, parsed.activate, parsed.target_ctx) == (True, False, 65536)
    assert parse_calibration_input("coding", None, ["--activate"]).activate is True
    with pytest.raises(CalibrationError):
        parse_calibration_input("coding", None, ["--candidate", "safe:8192"])
    with pytest.raises(CalibrationError):
        parse_calibration_input("coding", None, ["--target-ctx"])
    with pytest.raises(CalibrationError):
        parse_calibration_input("coding", None, ["--target-ctx", "65536", "--target-ctx", "32768"])


def test_validation_rejects_conflicts_and_unapproved_context() -> None:
    """Reject conflicting activation and off-scale target contexts before hardware detection."""
    with pytest.raises(CalibrationError):
        _validate(CalibrationCliInput("coding", activate=True, no_activate=True))
    with pytest.raises(CalibrationError):
        _validate(CalibrationCliInput("coding", activate=True, target_ctx=65536))
    with pytest.raises(CalibrationError, match="cannot relabel"):
        _validate(CalibrationCliInput("coding", activate=True, preference="fast"))
    with pytest.raises(CalibrationError):
        _validate(CalibrationCliInput("coding", target_ctx=12345))
    _validate(CalibrationCliInput("coding", target_ctx=65536))


def test_activate_promotes_the_candidate_without_relabeling_it(monkeypatch) -> None:
    """Promote the candidate exactly as measured because it contains only one cell."""
    promoted: list[str] = []
    monkeypatch.setattr(
        calibration_cli,
        "promote_candidate",
        lambda mode_id: promoted.append(mode_id) or Path("record.json"),
    )

    calibration_cli._run(
        CalibrationCliInput("coding", activate=True),
        Console(quiet=True),
    )

    assert promoted == ["coding"]


@pytest.mark.parametrize("target_ctx", MEASURABLE_CONTEXT_SCALE)
def test_every_measurable_scale_step_is_an_approved_expert_target(target_ctx: int) -> None:
    """Accept each searched context as an explicit target."""
    _validate(CalibrationCliInput("coding", target_ctx=target_ctx))


@pytest.mark.parametrize("target_ctx", sorted(set(CONTEXT_SCALE) - set(MEASURABLE_CONTEXT_SCALE)))
def test_an_unmeasurable_target_is_refused_before_any_process_starts(target_ctx: int) -> None:
    """Explain that the pinned quick-bench request cannot fit, instead of failing after a trial."""
    with pytest.raises(CalibrationError, match="cannot be measured"):
        _validate(CalibrationCliInput("coding", target_ctx=target_ctx))


def test_outcome_shows_only_the_selected_preference_cell() -> None:
    """Explain the one result measured and stored for this mode."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    envelope = EnvelopeResult("max_context", sample(65536, 37, 100.0), GateResult(True, True, None))
    record_path = Path("/records/coding.json")
    evidence_path = Path("/evidence/run")
    result = RunResult(
        "a" * 32,
        (record_path,),
        (ModeResult(mode, envelope, (sample(65536, 37, 100.0),), ()),),
        evidence_path,
    )
    console = Console(record=True, width=200)
    show_outcome(result, console)
    text = console.export_text()
    assert "fast" not in text and "balanced" not in text
    assert "max_context" in text
    assert "n_cpu_moe=37" in text
    # Compare rendered paths, not POSIX literals: the separator differs per platform.
    assert str(evidence_path) in text


@pytest.mark.parametrize(
    "error",
    [
        SearchError("no feasible context step produced a usable sample"),
        UnclassifiableTrialError("unsupported trial error: ProcessError: broken"),
    ],
)
def test_a_failed_search_exits_operationally_without_a_traceback(monkeypatch, error) -> None:
    """Map every measured-run failure onto exit code 1, because the input itself was valid."""
    monkeypatch.setattr(calibration_cli, "prepare_target", lambda mode: object())
    monkeypatch.setattr(calibration_cli, "show_preflight", lambda *args: None)
    monkeypatch.setattr(calibration_cli.typer, "confirm", lambda *args, **kwargs: True)

    def failing(target, run_options):
        """Raise the parameterized operational calibration failure."""
        del target, run_options
        raise error

    monkeypatch.setattr(calibration_cli, "run_calibration", failing)

    with pytest.raises(typer.Exit) as exit_info:
        run_calibrate(CalibrationCliInput("coding"), *_output())

    assert exit_info.value.exit_code == 1


def test_declining_the_confirmation_cancels_with_the_contractual_code(monkeypatch) -> None:
    """Leave exit code 130 to an operator who declines before any process starts."""
    monkeypatch.setattr(calibration_cli, "prepare_target", lambda mode: object())
    monkeypatch.setattr(calibration_cli, "show_preflight", lambda *args: None)
    monkeypatch.setattr(calibration_cli.typer, "confirm", lambda *args, **kwargs: False)

    with pytest.raises(typer.Exit) as exit_info:
        run_calibrate(CalibrationCliInput("coding"), *_output())

    assert exit_info.value.exit_code == 130


def test_a_partial_run_prints_its_records_and_still_exits_operationally(monkeypatch) -> None:
    """Report what was measured, then refuse to call an incomplete run a success (D-067)."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    envelope = EnvelopeResult("balanced", sample(65536, 37, 100.0), GateResult(True, True, None))
    record_path = Path("/records/coding.json")
    result = RunResult(
        "a" * 32,
        (record_path,),
        (ModeResult(mode, envelope, (sample(65536, 37, 100.0),), ()),),
        Path("/evidence/run"),
        ("vstudio: (65536, 36) is no longer feasible",),
    )
    monkeypatch.setattr(calibration_cli, "prepare_target", lambda mode_value: object())
    monkeypatch.setattr(calibration_cli, "show_preflight", lambda *args: None)
    monkeypatch.setattr(calibration_cli.typer, "confirm", lambda *args, **kwargs: True)
    monkeypatch.setattr(calibration_cli, "run_calibration", lambda target, options: result)
    console = Console(record=True, width=200)

    with pytest.raises(typer.Exit) as exit_info:
        run_calibrate(CalibrationCliInput("all"), console, Console(quiet=True))

    text = console.export_text()
    assert exit_info.value.exit_code == 1
    # Compare rendered paths, not POSIX literals: the separator differs per platform.
    assert str(record_path) in text
    assert "vstudio" in text
    assert "partially" in text
