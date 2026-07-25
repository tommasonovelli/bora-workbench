"""Tests for atomic state recovery, start locking, identity checks, and idempotent control."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import psutil
import pytest

import bora_workbench._process_control as control
from bora_workbench._process_lock import StartLockError, acquire_start_lock
from bora_workbench._process_state import ServiceState, write_state
from bora_workbench.process import status_services, stop_services


def service_for(process: subprocess.Popen[str], root: Path, *, create_time: float | None = None):
    """Build a complete version-1 state entry for one harmless test child."""
    identity_time = (
        psutil.Process(process.pid).create_time() if create_time is None else create_time
    )
    return ServiceState(
        "llama-server",
        process.pid,
        identity_time,
        sys.executable,
        8080,
        "2026-07-16T00:00:00Z",
        str(root / "server.log"),
        "coding",
        "owner/model:file",
        "b10011",
        None,
        8192,
        None,
        "cpu",
        None,
    )


def sleeper() -> subprocess.Popen[str]:
    """Start a test-only Python child that performs no network or administrative work."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], text=True)


def test_status_and_stop_without_services_are_read_only_and_idempotent(tmp_path) -> None:
    """Return success with no state and do not create a directory just to report emptiness."""
    root = tmp_path / "absent"

    assert status_services(root).services == ()
    assert stop_services(root).stopped == ()
    assert not root.exists()


def test_corrupt_state_is_quarantined_and_rebuilt_empty(tmp_path) -> None:
    """Preserve malformed bytes under a timestamped name and warn instead of crashing."""
    root = tmp_path / "state"
    root.mkdir()
    (root / "services.json").write_text("{broken", encoding="utf-8")

    report = status_services(root)

    assert report.services == ()
    assert "Corrupt service state" in report.warnings[0]
    assert not (root / "services.json").exists()
    assert len(tuple(root.glob("services.corrupt-*.json"))) == 1


def test_pid_reuse_entry_is_removed_without_termination(tmp_path) -> None:
    """Treat a matching PID with a different create_time as stale and never signal it."""
    process = sleeper()
    try:
        stale = service_for(process, tmp_path, create_time=0.0)
        write_state(tmp_path, (stale,))

        report = status_services(tmp_path)

        assert report.services == ()
        assert process.poll() is None
        assert "Removed stale state" in report.warnings[0]
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_stop_terminates_only_exact_live_identity_and_clears_state(tmp_path) -> None:
    """Terminate a verified child and atomically retain an empty version-1 state."""
    process = sleeper()
    write_state(tmp_path, (service_for(process, tmp_path),))

    report = stop_services(tmp_path)

    assert report.stopped == ("llama-server",)
    assert process.poll() is not None
    payload = json.loads((tmp_path / "services.json").read_text(encoding="utf-8"))
    assert payload == {"version": 1, "services": []}


def test_stop_escalates_from_terminate_to_kill_after_ten_seconds(tmp_path, monkeypatch) -> None:
    """Apply the normative ten-second terminate and five-second kill sequence."""
    child = sleeper()
    try:
        service = service_for(child, tmp_path)
    finally:
        child.terminate()
        child.wait(timeout=5)
    fake = Mock()
    fake.is_running.return_value = True
    fake.create_time.return_value = service.create_time
    fake.wait.side_effect = [psutil.TimeoutExpired(10, pid=service.pid), None]
    monkeypatch.setattr(control.psutil, "Process", lambda pid: fake)

    assert control._terminate_service(service) is True
    fake.terminate.assert_called_once()
    fake.kill.assert_called_once()
    assert fake.wait.call_args_list[0].kwargs["timeout"] == 10
    assert fake.wait.call_args_list[1].kwargs["timeout"] == 5


def test_stop_skips_process_dying_between_recheck_and_terminate(tmp_path, monkeypatch) -> None:
    """Treat NoSuchProcess raised by terminate as already stopped instead of a control error."""
    child = sleeper()
    try:
        service = service_for(child, tmp_path)
    finally:
        child.terminate()
        child.wait(timeout=5)
    fake = Mock()
    fake.is_running.return_value = True
    fake.create_time.return_value = service.create_time
    fake.terminate.side_effect = psutil.NoSuchProcess(service.pid)
    monkeypatch.setattr(control.psutil, "Process", lambda pid: fake)

    assert control._terminate_service(service) is False
    fake.kill.assert_not_called()


def test_live_start_lock_rejects_second_launch(tmp_path) -> None:
    """Reject concurrent preflight while the exact owner remains alive."""
    first = acquire_start_lock(tmp_path)
    try:
        with pytest.raises(StartLockError, match="already in progress"):
            acquire_start_lock(tmp_path)
    finally:
        first.release()
    assert not (tmp_path / "start.lock").exists()


def test_certainly_stale_start_lock_is_removed_and_retried_once(tmp_path) -> None:
    """Replace a dead owner record and release only the newly acquired identity."""
    tmp_path.mkdir(exist_ok=True)
    stale = {"pid": 999_999_999, "create_time": 0.0}
    (tmp_path / "start.lock").write_text(json.dumps(stale), encoding="utf-8")

    with acquire_start_lock(tmp_path) as lock:
        owner = json.loads((tmp_path / "start.lock").read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert lock.is_owned

    assert not (tmp_path / "start.lock").exists()
