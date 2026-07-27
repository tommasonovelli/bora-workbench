"""Identify this uv tool installation and run one uv command after the process has exited.

Windows cannot delete or replace the virtual environment of the process that is still executing,
so `uninstall` and `update` both need their uv invocation to happen afterwards. The handoff starts
a helper on the base interpreter, proves the helper is the one that was started, and lets it detect
this process exiting (specification sections 5.10-5.12). It lives in its own module because it
belongs to neither command in particular.

The helper detects parent exit by watching the accepted socket close, so the channel and the child
handle must outlive `schedule_uv_command`. Module-level references keep the file descriptor open
until the interpreter itself tears down.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_TOOL_NAME = "bora-workbench"
_HANDOFF_TIMEOUT_SECONDS = 5.0

_HANDOFF_CHANNELS: list[socket.socket] = []
_HELPER_PROCESSES: list[subprocess.Popen[bytes]] = []


class ToolHandoffError(RuntimeError):
    """Report an actionable failure to inspect uv or to schedule a deferred uv command."""


@dataclass(frozen=True, slots=True)
class ToolInstallation:
    """Describe whether this invocation belongs to the uv-managed tool environment."""

    environment: Path
    uv_executable: Path | None

    @property
    def is_managed_by_uv(self) -> bool:
        """Return whether uv can safely replace or remove this exact running installation."""
        return self.uv_executable is not None


@dataclass(frozen=True, slots=True)
class _Handoff:
    """Group the proof token and uv arguments of one scheduled command."""

    token: str
    arguments: tuple[str, ...]


def _query_tool_root(uv_executable: Path) -> Path:
    """Ask uv for its configured tool root without performing network access."""
    try:
        result = subprocess.run(
            [str(uv_executable), "tool", "dir"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ToolHandoffError(f"could not inspect the uv tool directory: {error}") from error
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or f"uv exited with code {result.returncode}"
        raise ToolHandoffError(f"could not inspect the uv tool directory: {detail}")
    return Path(result.stdout.strip()).resolve()


def inspect_tool_installation() -> ToolInstallation:
    """Identify only an exact bora-workbench environment managed by the available uv."""
    environment = Path(sys.prefix).resolve()
    located = shutil.which("uv")
    if located is None:
        return ToolInstallation(environment, None)
    uv_executable = Path(located).resolve()
    expected = (_query_tool_root(uv_executable) / _TOOL_NAME).resolve()
    receipt = expected / "uv-receipt.toml"
    if environment != expected or not receipt.is_file():
        return ToolInstallation(environment, None)
    return ToolInstallation(environment, uv_executable)


def _helper_command(installation: ToolInstallation, handoff: _Handoff, port: int) -> list[str]:
    """Build the base-interpreter helper command that survives tool environment replacement."""
    base_executable = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    if not base_executable.is_file() or installation.uv_executable is None:
        raise ToolHandoffError("cannot find the base Python or uv executable for the uv handoff")
    return [
        str(base_executable),
        "-m",
        "bora_workbench._tool_helper",
        str(port),
        handoff.token,
        str(installation.uv_executable),
        *handoff.arguments,
    ]


def _receive_token(channel: socket.socket, size: int) -> bytes:
    """Read exactly one fixed-size handoff token from the local stream socket."""
    received = bytearray()
    while len(received) < size:
        chunk = channel.recv(size - len(received))
        if not chunk:
            break
        received.extend(chunk)
    return bytes(received)


def _accept_helper(listener: socket.socket, token: str) -> socket.socket:
    """Require the local helper to prove it received the unguessable handoff token."""
    listener.settimeout(_HANDOFF_TIMEOUT_SECONDS)
    expected = token.encode("ascii")
    try:
        channel, _ = listener.accept()
        received = _receive_token(channel, len(expected))
    except OSError as error:
        raise ToolHandoffError(f"deferred uv helper did not start: {error}") from error
    if not secrets.compare_digest(received, expected):
        channel.close()
        raise ToolHandoffError("deferred uv helper returned an invalid handoff token")
    return channel


def _terminate_helper(helper: subprocess.Popen[bytes]) -> None:
    """Reap a helper that failed its startup handshake without leaving a child process."""
    if helper.poll() is None:
        helper.terminate()
    try:
        helper.wait(timeout=_HANDOFF_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        helper.kill()
        helper.wait()


def _start_helper(installation: ToolInstallation, handoff: _Handoff) -> None:
    """Start and authenticate one helper bound to an already listening loopback socket."""
    module_root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(module_root)
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            command = _helper_command(installation, handoff, listener.getsockname()[1])
            helper = subprocess.Popen(command, stdin=subprocess.DEVNULL, env=environment)
            try:
                channel = _accept_helper(listener, handoff.token)
            except ToolHandoffError:
                _terminate_helper(helper)
                raise
    except OSError as error:
        raise ToolHandoffError(f"could not start the deferred uv helper: {error}") from error
    _HELPER_PROCESSES.append(helper)
    _HANDOFF_CHANNELS.append(channel)


def schedule_uv_command(installation: ToolInstallation, arguments: tuple[str, ...]) -> None:
    """Run one uv command from a verified local helper once this process has exited."""
    if not installation.is_managed_by_uv:
        return
    _start_helper(installation, _Handoff(secrets.token_hex(16), arguments))
