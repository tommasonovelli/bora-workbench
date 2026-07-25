"""Test interactive and redirected calibration progress presentation."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from bora_workbench._calibration_progress import ProgressEvent
from bora_workbench._cli_calibration_progress import CalibrationProgress


def test_redirected_progress_prints_only_completed_trials() -> None:
    """Keep logs line-oriented while labeling the screening estimate as a cap projection."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None, width=120)
    started = ProgressEvent("coding", "screening", 0, 14, None, True)
    completed = ProgressEvent("coding", "screening", 1, 14, 110.0)

    with CalibrationProgress(console) as progress:
        progress(started)
        progress(completed)

    assert stream.getvalue() == "coding screening: 1/≤14; cap projection ≈ 1m 50s\n"


def test_terminal_progress_retains_a_phase_summary() -> None:
    """Use the Rich live branch and preserve elapsed history after its task clears."""
    stream = StringIO()
    now = [0.0]

    def get_time() -> float:
        """Return a deterministic monotonic value for the live display."""
        return now[0]

    console = Console(file=stream, force_terminal=True, color_system=None, width=120)
    with CalibrationProgress(console, get_time) as progress:
        progress(ProgressEvent("coding", "screening", 0, 14, None, True))
        now[0] = 120.0
        progress(ProgressEvent("coding", "screening", 1, 14, 110.0))

    rendered = stream.getvalue()
    assert "coding screening complete: 1 trial(s) in 2m 00s." in rendered
    assert "coding screening: 1/≤14" not in rendered


def test_terminal_progress_marks_an_interrupted_phase() -> None:
    """Close the live display and retain an honest stopped summary on exceptions."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, color_system=None, width=100)

    with pytest.raises(RuntimeError, match="stop"), CalibrationProgress(console) as progress:
        progress(ProgressEvent("studio", "confirmation", 0, 4, None, True))
        raise RuntimeError("stop")

    assert "studio confirmation stopped: 0 trial(s)" in stream.getvalue()


def test_completed_confirmation_survives_a_later_failure() -> None:
    """Do not call finished trial work stopped when candidate persistence fails later."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, color_system=None, width=100)

    with pytest.raises(RuntimeError, match="write"), CalibrationProgress(console) as progress:
        progress(ProgressEvent("coding", "confirmation", 4, 4, 0.0))
        raise RuntimeError("write failed")

    assert "coding confirmation complete: 4 trial(s)" in stream.getvalue()
