"""Skip tests whose fixture needs a symlink the host refuses to let the process create.

Creating a symbolic link on Windows requires a privilege a plain user account does not hold, so
these tests fail while *arranging* their fixture, before reaching the behavior they check. That
behavior is real and stays verified wherever the privilege exists, which includes the Ubuntu CI
job; a host that cannot build the fixture must report a skip rather than a failure, because a
permanently red test is one nobody reads when it turns red for a real reason (`AGENTS.md`: tests
stay independent of the host operating system).
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

import pytest


def supports_symlinks(directory: Path) -> bool:
    """Report whether this host lets the test process create a symbolic link."""
    probe = directory / ".symlink-probe"
    try:
        probe.symlink_to(directory)
    except OSError:
        return False
    with suppress(OSError):
        probe.unlink()
    return True


def require_symlinks(directory: Path) -> None:
    """Skip the calling test when its fixture cannot be built on this host."""
    if not supports_symlinks(directory):
        pytest.skip("this host does not grant the privilege needed to create a symlink")
