"""Serialize launch preflight with an exclusive pid/create_time ownership file."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil

from qwen_launcher._process_state import find_verified_process


class StartLockError(RuntimeError):
    """Report a concurrent or unverifiable launcher start lock."""


@dataclass(frozen=True, slots=True)
class _Owner:
    """Identify the process that exclusively owns one launch preflight."""

    pid: int
    create_time: float


def _read_owner(path: Path) -> _Owner:
    """Read a complete lock owner or refuse unsafe stale-lock assumptions."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {"pid", "create_time"}:
            raise ValueError("expected pid and create_time")
        owner = _Owner(value["pid"], value["create_time"])
        pid_is_int = isinstance(owner.pid, int) and not isinstance(owner.pid, bool)
        time_is_number = isinstance(owner.create_time, (int, float)) and not isinstance(
            owner.create_time, bool
        )
        if not pid_is_int or not time_is_number or owner.pid < 1 or owner.create_time < 0:
            raise ValueError("invalid process identity")
        return owner
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise StartLockError(f"cannot verify existing start lock {path}: {error}") from error


def _owner_alive(owner: _Owner) -> bool:
    """Return whether the lock still belongs to the exact recorded process."""
    try:
        return find_verified_process(owner.pid, owner.create_time) is not None
    except (psutil.AccessDenied, OSError) as error:
        raise StartLockError(f"cannot verify start-lock owner PID {owner.pid}: {error}") from error


def _create(path: Path, owner: _Owner) -> None:
    """Create and flush one exclusive ownership file without a shell or replacement."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        payload = (json.dumps(asdict(owner), sort_keys=True) + "\n").encode()
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(slots=True)
class StartLock:
    """Release a launch lock only while its on-disk owner still matches this instance."""

    path: Path
    owner: _Owner
    is_owned: bool = True

    def release(self) -> None:
        """Remove only this owner's lock, preserving a replacement created by another process."""
        if not self.is_owned:
            return
        try:
            current = _read_owner(self.path)
            if current == self.owner:
                self.path.unlink(missing_ok=True)
        finally:
            self.is_owned = False

    def __enter__(self) -> StartLock:
        """Return this already acquired lock."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Release ownership regardless of preflight outcome."""
        self.release()


def acquire_start_lock(root: Path) -> StartLock:
    """Acquire exclusively, removing one certainly dead owner and retrying once."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "start.lock"
    owner = _Owner(os.getpid(), psutil.Process().create_time())
    try:
        _create(path, owner)
        return StartLock(path, owner)
    except FileExistsError:
        existing = _read_owner(path)
        if _owner_alive(existing):
            message = f"another launch is already in progress (PID {existing.pid})"
            raise StartLockError(message) from None
        try:
            path.unlink()
            _create(path, owner)
        except (FileNotFoundError, FileExistsError) as error:
            raise StartLockError(
                "start lock changed while removing a stale owner; retry"
            ) from error
        return StartLock(path, owner)
