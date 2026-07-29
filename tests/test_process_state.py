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

import bora_workbench.process as lifecycle
from bora_workbench._process_state import (
    ServiceState,
    StartLockError,
    acquire_start_lock,
    inspect_state,
    write_state,
)
from bora_workbench.process import inspect_services, status_services, stop_services


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


def tree_bytes(root: Path) -> dict[str, bytes | None]:
    """Capture names and file bytes so a read-only operation cannot hide a mutation."""
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def test_read_only_inspection_does_not_create_an_absent_trial_root(tmp_path) -> None:
    """Treat any service root as absent without creating its trial runtime hierarchy."""
    root = tmp_path / "calibration" / "trials" / "runtime"

    report = inspect_services(root)

    assert report.services == report.stale_services == ()
    assert report.errors == ()
    assert not root.exists()


def test_read_only_inspection_preserves_corrupt_state_bytes(tmp_path) -> None:
    """Report unreadable state without quarantining, replacing, or deleting its bytes."""
    root = tmp_path / "state"
    root.mkdir()
    path = root / "services.json"
    path.write_bytes(b"{broken")
    before = tree_bytes(root)

    state = inspect_state(root)
    report = inspect_services(root)

    assert state.error is not None and "Unreadable service state" in state.error
    assert report.services == ()
    assert "Unreadable service state" in report.errors[0]
    assert tree_bytes(root) == before


def test_read_only_inspection_separates_live_and_stale_identity(tmp_path, monkeypatch) -> None:
    """Verify pid plus create time while preserving the exact state tree."""

    def reject_lock(root):
        """Fail if inspection enters the mutating lifecycle lock path."""
        raise AssertionError(f"inspection acquired the lifecycle lock for {root}")

    monkeypatch.setattr(lifecycle, "acquire_start_lock", reject_lock)
    process = sleeper()
    try:
        live = service_for(process, tmp_path)
        stale = service_for(process, tmp_path, create_time=0.0)
        write_state(tmp_path, (live, stale))
        before = tree_bytes(tmp_path)

        report = inspect_services(tmp_path)

        assert report.services == (live,)
        assert report.stale_services == (stale,)
        assert "Stale state" in report.warnings[0]
        assert report.errors == ()
        assert tree_bytes(tmp_path) == before
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_read_only_inspection_treats_unopenable_pid_as_stale(tmp_path, monkeypatch) -> None:
    """Apply D-071 to inspection because launcher children share the same account."""
    state = ServiceState(
        "llama-server",
        4321,
        1.0,
        sys.executable,
        8080,
        "2026-07-16T00:00:00Z",
        str(tmp_path / "server.log"),
        "coding",
        "owner/model:file",
        "b10011",
        None,
        8192,
        None,
        "cpu",
        None,
    )
    write_state(tmp_path, (state,))
    monkeypatch.setattr(
        lifecycle.psutil, "Process", lambda pid: (_ for _ in ()).throw(psutil.AccessDenied(pid))
    )

    report = inspect_services(tmp_path)

    assert report.services == ()
    assert report.stale_services == (state,)
    assert report.errors == ()


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
    monkeypatch.setattr(lifecycle.psutil, "Process", lambda pid: fake)

    assert lifecycle._terminate_service(service) is True
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
    monkeypatch.setattr(lifecycle.psutil, "Process", lambda pid: fake)

    assert lifecycle._terminate_service(service) is False
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


def test_status_and_stop_refuse_to_race_an_active_start_lock(tmp_path) -> None:
    """Never clean or clear a stale snapshot while a new service is being registered."""
    with acquire_start_lock(tmp_path):
        with pytest.raises(lifecycle.ProcessError, match="another launch"):
            status_services(tmp_path)
        with pytest.raises(lifecycle.ProcessError, match="another launch"):
            stop_services(tmp_path)


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
