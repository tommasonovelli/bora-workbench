"""Select an interactive or reduced terminal presentation before Textual is imported."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import TextIO

from bora_workbench.tui.motion import decide_motion

_LAYOUT_GLYPHS = "bora ─ ╭ ▸ · ~ overview"


@dataclass(frozen=True, slots=True)
class TerminalMode:
    """Describe whether the TUI can start and whether it should use reduced styling."""

    is_interactive: bool
    is_plain: bool
    plain_reason: str | None = None
    is_motion_enabled: bool = False
    motion_reason: str | None = None


def _is_tty(stream: TextIO) -> bool:
    """Return whether one current process stream is attached to a terminal."""
    try:
        return stream.isatty()
    except (OSError, ValueError):
        return False


def _has_interactive_streams() -> bool:
    """Require both input and output terminals so navigation and restoration are safe."""
    return _is_tty(sys.stdin) and _is_tty(sys.stdout)


def _has_layout_encoding() -> bool:
    """Return whether the output encoding can represent the normal bordered layout."""
    encoding = sys.stdout.encoding
    if encoding is None:
        return False
    try:
        _LAYOUT_GLYPHS.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _plain_reason(is_plain_requested: bool) -> str | None:
    """Return the first deterministic reason normal colour and motion are unavailable."""
    if is_plain_requested:
        return "requested with --plain"
    if os.environ.get("TERM", "").casefold() == "dumb":
        return "TERM=dumb"
    if "NO_COLOR" in os.environ:
        return "NO_COLOR is set"
    if not _has_layout_encoding():
        return "the output encoding is limited"
    return None


def inspect_terminal(is_plain_requested: bool) -> TerminalMode:
    """Choose presentation and optional motion after enforcing interactive streams."""
    if not _has_interactive_streams():
        return TerminalMode(False, True)
    plain_reason = _plain_reason(is_plain_requested)
    motion = decide_motion(plain_reason is not None, os.environ)
    return TerminalMode(
        True,
        plain_reason is not None,
        plain_reason,
        motion.is_enabled,
        motion.reason,
    )
