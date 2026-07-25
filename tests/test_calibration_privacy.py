"""Regression tests for the privacy scanner applied to shareable calibration content."""

from __future__ import annotations

import getpass
import socket

import pytest

from qwen_launcher._calibration_privacy import has_private_path_pattern, privacy_findings


@pytest.mark.parametrize(
    "text",
    [
        "/home/alice/private/model.gguf",
        "/Users/alice/models/model.gguf",
        r"C:\Users\Alice\model.gguf",
        r"\\fileserver\share\model.gguf",
        "/opt/models/model.gguf",
    ],
)
def test_generic_private_path_patterns_are_detected(text: str) -> None:
    """Recognize POSIX, Windows, and UNC absolute paths regardless of the running platform."""
    assert has_private_path_pattern(text)


@pytest.mark.parametrize(
    "text",
    ["unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_M", "ctx=131072 n_cpu_moe=38", "b10011"],
)
def test_shareable_identifiers_are_not_mistaken_for_paths(text: str) -> None:
    """Keep model identifiers and measured settings publishable without false positives."""
    assert not has_private_path_pattern(text)


def test_findings_report_local_identity_and_absolute_paths(tmp_path) -> None:
    """Name each offending file so a human review knows exactly what to fix."""
    (tmp_path / "clean.json").write_text('{"ctx": 131072}\n', encoding="utf-8")
    identity = f"user {getpass.getuser()} on {socket.gethostname()}"
    (tmp_path / "identity.json").write_text(identity, encoding="utf-8")
    (tmp_path / "path.json").write_text("/home/alice/model.gguf", encoding="utf-8")

    findings = dict(privacy_findings(tmp_path))

    assert "clean.json" not in findings
    assert "local username" in findings["identity.json"]
    assert "private absolute path" in findings["path.json"]
