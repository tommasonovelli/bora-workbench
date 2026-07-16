"""Persist version-1 service state atomically and validate process identity."""

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


def load_state(root: Path) -> StateSnapshot:
    """Read state, quarantining malformed JSON and reconstructing an empty snapshot."""
    path = _state_path(root)
    if not path.exists():
        return StateSnapshot(())
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("state version must equal 1")
        services = value.get("services")
        if not isinstance(services, list):
            raise ValueError("services must be an array")
        return StateSnapshot(tuple(_decode_service(item) for item in services))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
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
        process = psutil.Process(service.pid)
        return process.is_running() and process.create_time() == service.create_time
    except psutil.NoSuchProcess:
        return False
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
