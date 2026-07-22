"""Test plain-language calibration/v4 outcome summaries and expert hints."""

from __future__ import annotations

from dataclasses import replace
from io import StringIO

from rich.console import Console

from qwen_launcher._calibration_v4_types import ModeCalibration, V4Outcome
from qwen_launcher._cli_calibration_summary import show_calibration_outcome
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import cuda_calibration


def _render(calibration: ModeCalibration, tmp_path) -> str:
    """Render one synthetic active outcome to a non-interactive console."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None, width=200)
    outcome = V4Outcome(
        (calibration,),
        (),
        (tmp_path / "records" / "coding.json",),
        tmp_path / "evidence",
    )
    show_calibration_outcome(outcome, console)
    return stream.getvalue()


def test_summary_explains_selection_memory_and_automatic_96k_gap(tmp_path) -> None:
    """Make the selected fit interpretable without promising an unmeasured 96K fit."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    calibration = replace(cuda_calibration(mode), ctx=65536)

    rendered = _render(calibration, tmp_path)

    assert "selected the finalist that won both paired rounds" in rendered
    assert "RAM available min 20.00 GiB" in rendered
    assert "VRAM free min 2.40 GiB" in rendered
    assert "--target-ctx 98304 --no-activate" in rendered
    assert "feasibility is not implied" in rendered


def test_summary_hides_96k_hint_for_an_explicit_target(tmp_path) -> None:
    """Do not suggest a second expert run when the operator fixed the context."""
    mode = load_catalog().mode("coding")
    assert mode is not None
    calibration = replace(cuda_calibration(mode), ctx=65536, target_ctx=65536)

    assert "--target-ctx 98304" not in _render(calibration, tmp_path)
