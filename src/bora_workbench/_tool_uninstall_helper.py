"""Remove bora-workbench with uv after the invoking Python process has exited."""

from __future__ import annotations

import socket
import subprocess
import sys
import time

_EXIT_GRACE_SECONDS = 0.25


def _wait_for_handoff(port: int, token: str) -> None:
    """Prove helper startup, then wait for the parent-held channel to close at process exit."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as channel:
        channel.sendall(token.encode("ascii"))
        channel.settimeout(None)
        while channel.recv(1):
            pass


def _run_uv(uv_executable: str) -> int:
    """Invoke the exact discovered uv executable without a shell and expose its result."""
    try:
        result = subprocess.run([uv_executable, "tool", "uninstall", "bora-workbench"], check=False)
    except OSError as error:
        print(f"Uninstall error: could not run uv: {error}", file=sys.stderr)
        return 1
    if result.returncode != 0:
        print(
            f"Uninstall error: uv tool removal exited with code {result.returncode}",
            file=sys.stderr,
        )
    return result.returncode


def main() -> int:
    """Validate helper arguments, await parent teardown, and delegate package removal to uv."""
    if len(sys.argv) != 4:
        print("Uninstall error: invalid tool-removal handoff", file=sys.stderr)
        return 1
    try:
        port = int(sys.argv[1])
        _wait_for_handoff(port, sys.argv[2])
    except (OSError, ValueError) as error:
        print(f"Uninstall error: tool-removal handoff failed: {error}", file=sys.stderr)
        return 1
    time.sleep(_EXIT_GRACE_SECONDS)
    return _run_uv(sys.argv[3])


if __name__ == "__main__":
    raise SystemExit(main())
