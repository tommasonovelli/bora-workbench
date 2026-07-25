"""Test interactive and redirected managed-engine progress presentation."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from bora_workbench._cli_engine_progress import EngineInstallProgress
from bora_workbench._engine_types import InstallProgressEvent


def test_redirected_progress_prints_each_phase_once() -> None:
    """Keep redirected logs durable without printing one line per byte chunk."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None, width=120)

    with EngineInstallProgress(console) as progress:
        progress(InstallProgressEvent("asset", "engine.zip", 1, 1))
        progress(InstallProgressEvent("download", "engine.zip", 1, 1, 0, 100))
        progress(InstallProgressEvent("download", "engine.zip", 1, 1, 50, 100))
        progress(InstallProgressEvent("extract", "engine.zip", 1, 1))
        progress(InstallProgressEvent("extract", "engine.zip", 1, 1, 100, 100))
        progress(InstallProgressEvent("verify"))

    assert stream.getvalue().splitlines() == [
        "Checking locked asset [1/1] engine.zip.",
        "Downloading [1/1] engine.zip.",
        "Extracting [1/1] engine.zip.",
        "Verifying llama-server version and help contracts.",
    ]


def test_redirected_progress_identifies_cached_assets() -> None:
    """Do not present a checksum-verified cache hit as a network download."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None)
    event = InstallProgressEvent("download", "engine.zip", 1, 2, 100, 100, True)

    with EngineInstallProgress(console) as progress:
        progress(event)

    assert stream.getvalue() == "Using verified cached asset [1/2] engine.zip.\n"


def test_terminal_progress_shows_byte_bar_and_eta() -> None:
    """Calculate an ETA beside the live bar from measured bytes and elapsed time."""
    stream = StringIO()
    now = [0.0]

    def get_time() -> float:
        """Return deterministic monotonic time for transfer-rate calculation."""
        return now[0]

    console = Console(file=stream, force_terminal=True, color_system=None, width=120)
    with EngineInstallProgress(console, get_time) as progress:
        progress(InstallProgressEvent("download", "engine.zip", 1, 2, 0, 100))
        now[0] = 5.0
        progress(InstallProgressEvent("download", "engine.zip", 1, 2, 50, 100))

    rendered = stream.getvalue()
    assert "50.0 B/100.0 B · 10.0 B/s" in rendered
    assert "ETA ≈ 5s" in rendered
    assert "Downloading [1/2] engine.zip complete in 5s." in rendered


def test_terminal_progress_shows_compile_percentage() -> None:
    """Render the real CMake percentage beside the compile bar as it advances."""
    stream = StringIO()
    now = [0.0]

    def get_time() -> float:
        """Return deterministic monotonic time so each percentage forces a refresh."""
        return now[0]

    console = Console(file=stream, force_terminal=True, color_system=None, width=120)
    with EngineInstallProgress(console, get_time) as progress:
        progress(InstallProgressEvent("compile"))
        now[0] = 1.0
        progress(InstallProgressEvent("compile", percent=42))
        now[0] = 2.0
        progress(InstallProgressEvent("compile", percent=100))

    rendered = stream.getvalue()
    assert "Configuring and compiling Ubuntu CUDA llama-server" in rendered
    assert "42%" in rendered
    assert "100%" in rendered


def test_terminal_progress_marks_an_interrupted_transfer() -> None:
    """Retain a stopped summary when a measured operation raises an error."""
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, color_system=None, width=100)

    with pytest.raises(RuntimeError, match="stop"), EngineInstallProgress(console) as progress:
        progress(InstallProgressEvent("extract", "engine.zip", 1, 1, 25, 100))
        raise RuntimeError("stop")

    assert "Extracting [1/1] engine.zip stopped" in stream.getvalue()
