"""Test plain-language calibration/v5 outcome summaries."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from qwen_launcher._calibration_v5_types import ModeCalibration, V5Outcome
from qwen_launcher._cli_calibration_summary import show_calibration_outcome
from qwen_launcher.profiles import load_catalog
from tests.record_fixtures import cuda_calibration


def _render(calibration: ModeCalibration, tmp_path) -> str:
    """Render one synthetic active outcome to a non-interactive console."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None, width=200)
    outcome = V5Outcome(
        (calibration,),
        (),
        (tmp_path / "records" / "coding.json",),
        tmp_path / "evidence",
    )
    show_calibration_outcome(outcome, console)
    return stream.getvalue()


def test_summary_explains_selection_and_memory(tmp_path) -> None:
    """Make the selected fit and its measured headroom interpretable."""
    mode = load_catalog().mode("coding")
    assert mode is not None

    rendered = _render(cuda_calibration(mode), tmp_path)

    assert "selected the finalist that won both paired rounds" in rendered
    assert "RAM available min 20.00 GiB" in rendered
    assert "VRAM free min 2.40 GiB" in rendered
