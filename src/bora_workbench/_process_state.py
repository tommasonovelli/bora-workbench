"""Persist version-1 service state atomically, verify process identity, and own the start lock.

Both files below live in the state root and share one primitive: the mandatory pid plus create_time
identity of specification section 5.9. A recorded PID alone is never trusted, because the operating
system may already have given it to an unrelated process, and acting on that would terminate a
stranger. Every write replaces the target through a flushed same-directory temporary file, so a
crash can leave the previous file or the new one, never a half-written state.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psutil


class StateError(RuntimeError):
    """Report state that cannot be read, verified, or updated safely."""


class StartLockError(RuntimeError):
    """Report a concurrent or unverifiable launcher start lock."""


@dataclass(frozen=True, slots=True)
class ServiceState:
    """Record the process identity and launch plan needed by status and safe stop."""

    label: str
    pid: int
    create_time: float
    executable: str
    port: int
    started_at: str
    log_path: str
    mode: str
    model: str
    engine_release: str
    profile_id: str | None
    ctx: int
    n_cpu_moe: int | None
    backend: str
    gpu_index: int | None


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """Return live services together with cleanup diagnostics."""

    services: tuple[ServiceState, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StateInspection:
    """Return decoded state or one read error without mutating its source (D-084)."""

    services: tuple[ServiceState, ...]
    error: str | None = None


def find_verified_process(pid: int, create_time: float) -> psutil.Process | None:
    """Return the live process only when pid and create_time both match, or None otherwise.

    The pid/create_time pair is the mandatory process identity from specification section 5.9.
    A process this account cannot open is never a service this launcher started, because the
    launcher and its children share one account: on Windows, where PIDs are recycled quickly, that
    is the recorded PID having been reused by a stranger. Reporting it as absent keeps the record
    clearable, while the callers that act on a service still send no signal to anything they could
    not verify (D-071).
    """
    try:
        process = psutil.Process(pid)
        if process.is_running() and process.create_time() == create_time:
            return process
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return None
    return None


def _state_path(root: Path) -> Path:
    """Return the versioned service-state file below the supplied state root."""
    return root / "services.json"


def _has_valid_types(service: ServiceState) -> bool:
    """Reject bool-as-int and malformed scalar fields before any PID can be inspected."""
    strings = (
        service.label,
        service.executable,
        service.started_at,
        service.log_path,
        service.mode,
        service.model,
        service.engine_release,
        service.backend,
    )
    integers = (service.pid, service.port, service.ctx)
    optional_integers = (service.n_cpu_moe, service.gpu_index)
    return (
        all(isinstance(item, str) and item for item in strings)
        and all(isinstance(item, int) and not isinstance(item, bool) for item in integers)
        and all(
            item is None or (isinstance(item, int) and not isinstance(item, bool))
            for item in optional_integers
        )
        and isinstance(service.create_time, (int, float))
        and not isinstance(service.create_time, bool)
        and (service.profile_id is None or isinstance(service.profile_id, str))
    )


def _decode_service(value: object) -> ServiceState:
    """Construct one service record while rejecting malformed required fields."""
    if not isinstance(value, dict):
        raise ValueError("service entry must be an object")
    fields = ServiceState.__dataclass_fields__
    if not set(fields).issubset(value):
        raise ValueError("service entry is missing required fields")
    selected = {name: value[name] for name in fields}
    service = ServiceState(**selected)  # type: ignore[arg-type]
    if not _has_valid_types(service):
        raise ValueError("service fields have invalid types")
    if service.pid < 1 or service.create_time < 0 or service.backend not in {"cpu", "cuda"}:
        raise ValueError("service identity or backend is invalid")
    return service


def _quarantine(path: Path) -> Path:
    """Atomically preserve malformed state under a timestamped diagnostic name."""
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    destination = path.with_name(f"services.corrupt-{stamp}.json")
    try:
        path.replace(destination)
    except OSError as error:
        raise StateError(f"cannot quarantine corrupt state {path}: {error}") from error
    return destination


_STATE_READ_ERRORS = (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError)


def _read_services(path: Path) -> tuple[ServiceState, ...]:
    """Decode one complete version-1 state file without applying a recovery policy."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("state version must equal 1")
    services = value.get("services")
    if not isinstance(services, list):
        raise ValueError("services must be an array")
    return tuple(_decode_service(item) for item in services)


def inspect_state(root: Path) -> StateInspection:
    """Read state without locks, quarantine, cleanup, directory creation, or writes."""
    path = _state_path(root)
    try:
        if not path.exists():
            return StateInspection(())
        return StateInspection(_read_services(path))
    except _STATE_READ_ERRORS as error:
        return StateInspection((), f"Unreadable service state at {path}: {error}")


def load_state(root: Path) -> StateSnapshot:
    """Read state, quarantining malformed JSON and reconstructing an empty snapshot."""
    path = _state_path(root)
    if not path.exists():
        return StateSnapshot(())
    try:
        return StateSnapshot(_read_services(path))
    except _STATE_READ_ERRORS as error:
        quarantined = _quarantine(path)
        warning = f"Corrupt service state was moved to {quarantined}: {error}"
        return StateSnapshot((), (warning,))


def write_state(root: Path, services: tuple[ServiceState, ...]) -> None:
    """Replace state using a flushed same-directory temporary file."""
    root.mkdir(parents=True, exist_ok=True)
    path = _state_path(root)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    payload = {"version": 1, "services": [asdict(service) for service in services]}
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(payload, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise StateError(f"cannot update service state {path}: {error}") from error


def is_same_process(service: ServiceState) -> bool:
    """Match the mandatory pid plus create_time identity without guessing on access errors."""
    try:
        return find_verified_process(service.pid, service.create_time) is not None
    except (psutil.AccessDenied, OSError) as error:
        raise StateError(
            f"cannot verify process identity for PID {service.pid}: {error}"
        ) from error


def clean_state(root: Path) -> StateSnapshot:
    """Remove dead or PID-reused entries while retaining all verified live services."""
    snapshot = load_state(root)
    live: list[ServiceState] = []
    warnings = list(snapshot.warnings)
    for service in snapshot.services:
        if is_same_process(service):
            live.append(service)
        else:
            warnings.append(f"Removed stale state for {service.label} PID {service.pid}.")
    services = tuple(live)
    if services != snapshot.services:
        write_state(root, services)
    return StateSnapshot(services, tuple(warnings))


def remove_service(root: Path, service: ServiceState) -> None:
    """Atomically remove only the exact pid/create_time service record."""
    snapshot = load_state(root)
    retained = tuple(
        item
        for item in snapshot.services
        if (item.pid, item.create_time) != (service.pid, service.create_time)
    )
    if retained != snapshot.services:
        write_state(root, retained)


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
