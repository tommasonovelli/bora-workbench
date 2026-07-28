"""Remember which model artifacts already matched their locked digest (spec 5.8, D-076).

Verifying the pinned artifacts reads about 22 GiB, which every ``calibrate`` and every mode launch
paid again even when nothing had changed. A receipt records what a successful verification observed,
so a later run recomputes the SHA-256 only when the file, the lock, or the cache says it must.

The receipt is an optimization, never an authority: it can only *skip* work that a previous full
verification already did, a caller still checks the locked filename and byte size itself, and every
failure to read or write it degrades to hashing the file again.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from bora_workbench.paths import cache_dir

JsonObject = dict[str, object]

VerifyProgress = Callable[[int, int], None]

_SCHEMA = "model-verification/v1"
_RECEIPT_NAME = "model-verification.json"


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """Hold everything that must still hold for a previous verification to remain valid.

    ``expected_sha256`` belongs here because a changed ``engine.lock`` must invalidate a receipt
    that the untouched file on disk would otherwise still match.
    """

    path: Path
    size_bytes: int
    mtime_ns: int
    expected_sha256: str


def receipt_path() -> Path:
    """Return the receipt file, which lives under the cache root because it is regenerable."""
    return cache_dir() / _RECEIPT_NAME


def _load(path: Path) -> JsonObject:
    """Read the stored receipts, treating anything unreadable or foreign as no receipts at all."""
    try:
        decoded = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(decoded, dict) or decoded.get("schema") != _SCHEMA:
        return {}
    artifacts = decoded.get("artifacts")
    return artifacts if isinstance(artifacts, dict) else {}


def _entry(identity: ArtifactIdentity) -> JsonObject:
    """Serialize one artifact's observed identity."""
    return {
        "size_bytes": identity.size_bytes,
        "mtime_ns": identity.mtime_ns,
        "sha256": identity.expected_sha256,
    }


def is_verified(identity: ArtifactIdentity) -> bool:
    """Report whether a stored receipt already proved this exact artifact against this digest."""
    stored = _load(receipt_path()).get(str(identity.path))
    return isinstance(stored, dict) and stored == _entry(identity)


def remember(identity: ArtifactIdentity) -> None:
    """Record one successful verification, leaving the cache untouched when it cannot be written.

    A launch must not fail because a cache root is missing or read-only, so every filesystem error
    here is swallowed: the only consequence is that the next run hashes the file again.
    """
    path = receipt_path()
    artifacts = _load(path)
    artifacts[str(identity.path)] = _entry(identity)
    _write(path, {"schema": _SCHEMA, "artifacts": artifacts})


def forget(path: Path) -> None:
    """Drop one artifact's receipt, so removing a file also removes what was claimed about it.

    `remember` is what `pull` writes, so `rm` owes the symmetric write: a receipt naming a file that
    no longer exists claims a verification for bytes nobody can check. Like `remember`, this is
    best-effort — a receipt that cannot be rewritten costs a later rehash, never a failed removal.
    """
    receipt = receipt_path()
    artifacts = _load(receipt)
    if artifacts.pop(str(path), None) is None:
        return
    _write(receipt, {"schema": _SCHEMA, "artifacts": artifacts})


def _write(path: Path, document: JsonObject) -> None:
    """Replace the receipt atomically, leaving the cache untouched when it cannot be written."""
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(document, output, indent=2, ensure_ascii=False, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    except OSError:
        return
    finally:
        _discard(temporary)


def _discard(temporary: Path) -> None:
    """Remove one abandoned temporary receipt without reporting a cache that resists cleanup."""
    try:
        temporary.unlink(missing_ok=True)
    except OSError:
        return
