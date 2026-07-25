"""Identify and hand off removal of the current uv-managed tool environment.

The handoff runs from the base interpreter because Windows cannot remove the virtual environment
of the Python process that is still executing this command. The helper waits for this process to
exit, then invokes uv without a shell (specification sections 5.10-5.12).
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


class ToolUninstallError(RuntimeError):
    """Report an actionable failure to inspect or schedule uv tool removal."""


@dataclass(frozen=True, slots=True)
class ToolInstallation:
    """Describe whether this invocation belongs to the uv-managed tool environment."""

    environment: Path
    uv_executable: Path | None

    @property
    def is_managed_by_uv(self) -> bool:
        """Return whether uv can safely remove this exact running installation."""
        return self.uv_executable is not None


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
        raise ToolUninstallError(f"could not inspect the uv tool directory: {error}") from error
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or f"uv exited with code {result.returncode}"
        raise ToolUninstallError(f"could not inspect the uv tool directory: {detail}")
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


def _helper_command(installation: ToolInstallation, port: int, token: str) -> list[str]:
    """Build the base-interpreter helper command that survives tool environment removal."""
    base_executable = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
    if not base_executable.is_file() or installation.uv_executable is None:
        raise ToolUninstallError("cannot find the base Python or uv executable for tool removal")
    return [
        str(base_executable),
        "-m",
        "bora_workbench._tool_uninstall_helper",
        str(port),
        token,
        str(installation.uv_executable),
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
        raise ToolUninstallError(f"tool-removal helper did not start: {error}") from error
    if not secrets.compare_digest(received, expected):
        channel.close()
        raise ToolUninstallError("tool-removal helper returned an invalid handoff token")
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


def schedule_tool_removal(installation: ToolInstallation) -> None:
    """Start a verified local helper that removes the uv tool after this process exits."""
    if not installation.is_managed_by_uv:
        return
    token = secrets.token_hex(16)
    module_root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(module_root)
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            command = _helper_command(installation, listener.getsockname()[1], token)
            helper = subprocess.Popen(command, stdin=subprocess.DEVNULL, env=environment)
            try:
                channel = _accept_helper(listener, token)
            except ToolUninstallError:
                _terminate_helper(helper)
                raise
    except OSError as error:
        raise ToolUninstallError(f"could not start the tool-removal helper: {error}") from error
    _HELPER_PROCESSES.append(helper)
    _HANDOFF_CHANNELS.append(channel)
