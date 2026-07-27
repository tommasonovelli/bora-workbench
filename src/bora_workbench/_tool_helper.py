"""Run one uv command after the invoking bora-workbench process has exited.

`uninstall` hands over `tool uninstall` and `update` hands over `tool install --force`; both must
happen once the tool environment is no longer in use, which is why this module runs on the base
interpreter and never imports anything from the environment uv is about to replace.
"""

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


def _run_uv(uv_executable: str, arguments: list[str]) -> int:
    """Invoke the exact discovered uv executable without a shell and expose its result."""
    try:
        result = subprocess.run([uv_executable, *arguments], check=False)
    except OSError as error:
        print(f"bora: could not run uv: {error}", file=sys.stderr)
        return 1
    if result.returncode != 0:
        printable = " ".join(arguments)
        print(
            f"bora: `uv {printable}` exited with code {result.returncode}; "
            "run that command yourself to see the full failure",
            file=sys.stderr,
        )
    return result.returncode


def main() -> int:
    """Validate helper arguments, await parent teardown, and delegate the work to uv."""
    if len(sys.argv) < 5:
        print("bora: invalid deferred uv handoff", file=sys.stderr)
        return 1
    try:
        port = int(sys.argv[1])
        _wait_for_handoff(port, sys.argv[2])
    except (OSError, ValueError) as error:
        print(f"bora: deferred uv handoff failed: {error}", file=sys.stderr)
        return 1
    time.sleep(_EXIT_GRACE_SECONDS)
    return _run_uv(sys.argv[3], sys.argv[4:])


if __name__ == "__main__":
    raise SystemExit(main())
