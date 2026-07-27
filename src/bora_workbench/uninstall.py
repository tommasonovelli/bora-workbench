"""Remove the exact public managed roots and hand the uv tool environment to a helper.

Uninstall deletes managed data, cache, state, and configuration after a single confirmation, never
touches the Hugging Face cache, and stays idempotent (specification sections 5.2, 5.10, and 5.12).
Confined removal lives here so `cli.py` keeps to presentation and exit-code mapping (section 4.1).

The Python tool is removed from a detached helper running on the base interpreter, because Windows
cannot delete the virtual environment of the process that is still executing this command. That
handoff is shared with `update` and lives in `_tool_handoff.py`.

Nothing here branches on the operating system: the four public roots already come from `paths.py`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from bora_workbench._tool_handoff import ToolInstallation, schedule_uv_command
from bora_workbench.paths import cache_dir, config_dir, data_dir, state_dir

_TOOL_NAME = "bora-workbench"


class UninstallError(RuntimeError):
    """Signal an actionable uninstall failure mapped to exit code 1 without a traceback."""


@dataclass(frozen=True, slots=True)
class ManagedRoot:
    """Name one public managed root and whether it currently exists on disk."""

    label: str
    path: Path
    exists: bool


@dataclass(frozen=True, slots=True)
class RemovalReport:
    """Report which managed roots were deleted and which were already absent."""

    removed: tuple[Path, ...]
    absent: tuple[Path, ...]


def _named_roots() -> tuple[tuple[str, Path], ...]:
    """Return the four exact public roots allowed by specification section 5.2."""
    return (
        ("configuration", config_dir()),
        ("data", data_dir()),
        ("cache", cache_dir()),
        ("state", state_dir()),
    )


def managed_roots() -> tuple[ManagedRoot, ...]:
    """Return the exact configuration, data, cache, and state roots as a removal preview.

    The Hugging Face cache is excluded from the deletion set by construction (section 5.10).
    """
    return tuple(
        ManagedRoot(label, path, path.exists() or path.is_symlink())
        for label, path in _named_roots()
    )


def _remove_one(path: Path) -> bool:
    """Delete exactly one managed root and report whether it existed.

    Removal is confined to the given root: a symlinked root is refused rather than followed, so
    deletion can never escape the managed tree, and an absent root is a no-op that keeps uninstall
    idempotent (specification sections 5.10 and 5.12).
    """
    if path.is_symlink():
        raise UninstallError(f"refusing to remove a symlinked managed root: {path}")
    if not path.exists():
        return False
    try:
        shutil.rmtree(path)
    except OSError as error:
        raise UninstallError(f"could not remove {path}: {error}") from error
    return True


def _validate_roots(roots: tuple[ManagedRoot, ...]) -> None:
    """Refuse any deletion set other than the current exact public roots (section 5.10)."""
    expected = _named_roots()
    actual = tuple((root.label, root.path) for root in roots)
    if actual != expected:
        raise UninstallError("managed root set changed; refusing to remove anything")
    for root in roots:
        if root.exists and root.path.is_symlink():
            raise UninstallError(f"refusing to remove a symlinked managed root: {root.path}")
        if root.exists and not root.path.is_dir():
            raise UninstallError(f"managed root is not a directory: {root.path}")


def remove_managed_roots(roots: tuple[ManagedRoot, ...]) -> RemovalReport:
    """Delete roots present in the confirmed preview and leave later creations untouched."""
    _validate_roots(roots)
    removed: list[Path] = []
    absent: list[Path] = []
    for root in roots:
        if root.exists and _remove_one(root.path):
            removed.append(root.path)
        else:
            absent.append(root.path)
    return RemovalReport(tuple(removed), tuple(absent))


def schedule_tool_removal(installation: ToolInstallation) -> None:
    """Start a verified local helper that removes the uv tool after this process exits."""
    schedule_uv_command(installation, ("tool", "uninstall", _TOOL_NAME))
