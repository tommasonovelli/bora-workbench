"""Select an interactive or reduced terminal presentation before Textual is imported."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import TextIO

_LAYOUT_GLYPHS = "bora ─ overview"


@dataclass(frozen=True, slots=True)
class TerminalMode:
    """Describe whether the TUI can start and whether it should use reduced styling."""

    is_interactive: bool
    is_plain: bool
    plain_reason: str | None = None


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


def inspect_terminal(is_plain_requested: bool) -> TerminalMode:
    """Choose the normal or plain TUI only after enforcing the interactive-stream contract."""
    if not _has_interactive_streams():
        return TerminalMode(False, True)
    if is_plain_requested:
        return TerminalMode(True, True, "requested with --plain")
    if os.environ.get("TERM", "").casefold() == "dumb":
        return TerminalMode(True, True, "TERM=dumb")
    if not _has_layout_encoding():
        return TerminalMode(True, True, "the output encoding is limited")
    return TerminalMode(True, False)
