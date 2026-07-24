"""Offline tests for calibration/v6-lite CLI routing and pre-hardware validation."""

from __future__ import annotations

import pytest
import typer
from rich.console import Console

from qwen_launcher._cli_calibration import (
    CalibrationCliInput,
    CalibrationCliOutput,
    run_calibrate,
)
from qwen_launcher._cli_calibration_v6 import _preference, _validate
from qwen_launcher.calibration import CalibrationError


def _output() -> CalibrationCliOutput:
    """Return quiet CLI streams for exit-code assertions."""
    return CalibrationCliOutput(Console(quiet=True), Console(quiet=True))


def test_preference_requires_protocol_v6() -> None:
    """Reject --preference outside --protocol v6 with the contractual input exit code."""
    options = CalibrationCliInput("coding", (), None, protocol="v5", preference="fast")
    with pytest.raises(typer.Exit) as exit_info:
        run_calibrate(options, _output())
    assert exit_info.value.exit_code == 2


def test_preference_normalization_and_rejection() -> None:
    """Normalize max-context and reject an unknown preference before any process starts."""
    assert _preference("max-context") == "max_context"
    assert _preference(None) == "balanced"
    with pytest.raises(CalibrationError):
        _preference("turbo")


def test_v6_validation_rejects_conflicts_and_unapproved_context() -> None:
    """Reject conflicting activation and off-scale target contexts before hardware detection."""
    with pytest.raises(CalibrationError):
        _validate(CalibrationCliInput("coding", (), None, activate=True, no_activate=True))
    with pytest.raises(CalibrationError):
        _validate(CalibrationCliInput("coding", (), None, target_ctx=12345))
    _validate(CalibrationCliInput("coding", (), None, target_ctx=65536))
