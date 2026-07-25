"""Tests for the per-OS directory layout computed without touching the filesystem."""

from pathlib import Path

import bora_workbench.paths as paths


def test_linux_xdg_paths(monkeypatch):
    """Honor every XDG base directory variable when it names an absolute directory."""
    monkeypatch.setattr(paths, "_system_name", lambda: "linux")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: Path("/home/tester")))
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg/config")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg/data")
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg/cache")
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/xdg/state")

    assert paths.config_dir() == Path("/tmp/xdg/config/bora-workbench")
    assert paths.data_dir() == Path("/tmp/xdg/data/bora-workbench")
    assert paths.cache_dir() == Path("/tmp/xdg/cache/bora-workbench")
    assert paths.state_dir() == Path("/tmp/xdg/state/bora-workbench")


def test_linux_empty_or_relative_xdg_uses_fallback(monkeypatch):
    """Fall back to the XDG defaults when a variable is empty, relative, or absent."""
    monkeypatch.setattr(paths, "_system_name", lambda: "linux")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: Path("/home/tester")))
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    monkeypatch.setenv("XDG_DATA_HOME", "relative")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)

    assert paths.config_dir() == Path("/home/tester/.config/bora-workbench")
    assert paths.data_dir() == Path("/home/tester/.local/share/bora-workbench")
    assert paths.cache_dir() == Path("/home/tester/.cache/bora-workbench")
    assert paths.state_dir() == Path("/home/tester/.local/state/bora-workbench")


def test_windows_paths_can_be_simulated_on_linux(monkeypatch):
    """Split the shared LOCALAPPDATA root while keeping configuration under roaming APPDATA."""
    monkeypatch.setattr(paths, "_system_name", lambda: "windows")
    monkeypatch.setenv("APPDATA", r"C:\Users\Tester\AppData\Roaming")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Tester\AppData\Local")

    normalized = {
        "config": str(paths.config_dir()).replace("\\", "/"),
        "data": str(paths.data_dir()).replace("\\", "/"),
        "cache": str(paths.cache_dir()).replace("\\", "/"),
        "state": str(paths.state_dir()).replace("\\", "/"),
    }
    assert normalized == {
        "config": "C:/Users/Tester/AppData/Roaming/bora-workbench",
        "data": "C:/Users/Tester/AppData/Local/bora-workbench/data",
        "cache": "C:/Users/Tester/AppData/Local/bora-workbench/cache",
        "state": "C:/Users/Tester/AppData/Local/bora-workbench/state",
    }
