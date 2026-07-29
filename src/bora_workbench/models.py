"""Own the managed model store: how pinned weights arrive, where they live, and how they leave.

The launcher used to only *read* the model, which is why it could neither acquire nor release it.
The store under the data root is now the one location the tool writes and deletes, so `pull` and
`rm` never have to write into the shared Hugging Face cache (D-078). Launch resolution still
prefers the store and falls back to the pinned snapshot, so weights acquired before this store
existed keep working untouched.

Model artifacts reuse `_engine_assets` for the transfer itself: an engine archive and a GGUF have
the same requirements — HTTPS, a mandatory digest, and an atomic publish — and repeating that code
would mean maintaining two versions of the same care.

Nothing here branches on the operating system: every root comes from `paths.py`.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from bora_workbench._engine_assets import RemoteFile, TransferProgressCallback, download_file
from bora_workbench._model_removal import remove_cache_file
from bora_workbench._model_verification import ArtifactIdentity, forget, is_verified, remember
from bora_workbench.config import Config
from bora_workbench.engine import EngineError, JsonObject, hf_snapshot_dir
from bora_workbench.paths import models_dir

# The pinned revision is part of the URL, so a `pull` can only ever fetch the exact commit named by
# `engine.lock`: a moved branch or a re-uploaded file cannot silently change what arrives.
_RESOLVE_URL = "https://huggingface.co/{repository}/resolve/{revision}/{filename}"


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    """Describe one pinned artifact of the default model identity as a verifiable download."""

    label: str
    remote: RemoteFile
    size_bytes: int


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    """Report one existing copy of a pinned artifact and the bytes deleting it would free.

    `is_shared_cache` separates the two locations for every caller that has to treat them
    differently: the store belongs to this tool, the Hugging Face cache is shared with whatever
    else the machine runs (D-079).
    """

    artifact: ModelArtifact
    path: Path
    size_bytes: int
    is_shared_cache: bool


ArtifactStatus = Literal["absent", "wrong-size", "receipt-verified", "present-unverified"]
ArtifactLocation = Literal["managed-store", "hugging-face-cache", "user-managed"]


@dataclass(frozen=True, slots=True)
class ArtifactInspection:
    """Describe what a read-only check knows about one artifact at one location."""

    label: str
    path: Path
    location: ArtifactLocation
    status: ArtifactStatus
    size_bytes: int | None
    expected_size_bytes: int | None


@dataclass(frozen=True, slots=True)
class ModelInspection:
    """Collect receipt-aware model facts without hashing or writing (D-084)."""

    model: str
    is_managed: bool
    artifacts: tuple[ArtifactInspection, ...]
    diagnostics: tuple[str, ...] = ()

    @property
    def is_verified(self) -> bool:
        """Report whether every locked artifact has a receipt-verified copy."""
        if not self.is_managed:
            return False
        expected = {item.label for item in self.artifacts}
        verified = {item.label for item in self.artifacts if item.status == "receipt-verified"}
        return bool(expected) and expected == verified


def display_name(lock: JsonObject) -> str:
    """Return the short model name the API and the CLI both show (D-080)."""
    return cast(str, cast(JsonObject, lock["model_alias_contract"])["alias"])


def model_handle(lock: JsonObject) -> str:
    """Return the short name `pull` and `rm` accept on the command line."""
    return cast(str, lock["default_model_handle"])


def require_handle(lock: JsonObject, requested: str | None) -> None:
    """Accept the pinned model's own name, and refuse anything else by naming what exists.

    The argument is optional because there is exactly one pinned model, so `bora pull` and
    `bora pull qwen` are the same request. It is accepted at all so the command reads the way it
    will still read if a second model is ever pinned, and so a wrong name fails immediately instead
    of being silently understood as the default (D-078).
    """
    handle = model_handle(lock)
    if requested is not None and requested != handle:
        raise EngineError(f"unknown model {requested!r}; this distribution pins only {handle!r}")


def _artifact(label: str, model: JsonObject, spec: JsonObject) -> ModelArtifact:
    """Build one artifact whose download URL is pinned to the locked repository revision."""
    filename = cast(str, spec["filename"])
    url = _RESOLVE_URL.format(
        repository=cast(str, model["repository"]),
        revision=cast(str, model["revision"]),
        filename=filename,
    )
    remote = RemoteFile(filename, url, cast(str, spec["sha256"]))
    return ModelArtifact(label, remote, cast(int, spec["size_bytes"]))


def model_artifacts(lock: JsonObject) -> tuple[ModelArtifact, ...]:
    """Return the pinned weights and vision projector of the default model identity."""
    model = cast(JsonObject, lock["default_model_artifact"])
    projector = cast(JsonObject, model["mmproj"])
    return (_artifact("weights", model, model), _artifact("vision projector", model, projector))


def _identity(path: Path, artifact: ModelArtifact) -> ArtifactIdentity | None:
    """Build the receipt identity of a present, correctly sized file, or None when it is neither."""
    try:
        status = path.stat()
    except OSError:
        return None
    if status.st_size != artifact.size_bytes:
        return None
    digest = artifact.remote.sha256
    return ArtifactIdentity(path.absolute(), status.st_size, status.st_mtime_ns, digest)


def ensure_artifact(
    artifact: ModelArtifact, progress: TransferProgressCallback | None = None
) -> bool:
    """Leave a verified copy in the store and report whether it was already there.

    A receipt from an earlier verification short-circuits the digest check, because otherwise every
    `pull` of a complete model would reread about 22 GiB to learn nothing. After a real download the
    receipt is written here, so the first launch afterwards starts without hashing again (D-076).
    """
    store = models_dir()
    identity = _identity(store / artifact.remote.filename, artifact)
    if identity is not None and is_verified(identity):
        return True
    downloaded = download_file(artifact.remote, store, progress)
    verified = _identity(downloaded, artifact)
    if verified is not None:
        remember(verified)
    return False


def _snapshot_dir(lock: JsonObject) -> Path | None:
    """Return the pinned snapshot directory, or None when no Hugging Face cache can be named."""
    model = cast(JsonObject, lock["default_model_artifact"])
    try:
        return hf_snapshot_dir(model)
    except EngineError:
        return None


def repository_root(lock: JsonObject) -> Path | None:
    """Return the cached repository directory that confines every cache deletion."""
    snapshot = _snapshot_dir(lock)
    return None if snapshot is None else snapshot.parent.parent


def _copy_at(
    artifact: ModelArtifact, directory: Path, is_shared_cache: bool
) -> StoredArtifact | None:
    """Report one artifact's copy in one directory, ignoring anything that is not a real file."""
    path = directory / artifact.remote.filename
    if not path.is_file():
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    return StoredArtifact(artifact, path, size, is_shared_cache)


def locate_copies(lock: JsonObject) -> tuple[StoredArtifact, ...]:
    """List every existing copy of the pinned artifacts, store first and pinned snapshot second."""
    store = models_dir()
    snapshot = _snapshot_dir(lock)
    found: list[StoredArtifact] = []
    for artifact in model_artifacts(lock):
        found.append(_copy_at(artifact, store, False))
        if snapshot is not None:
            found.append(_copy_at(artifact, snapshot, True))
    return tuple(copy for copy in found if copy is not None)


def _inspect_artifact(
    artifact: ModelArtifact, path: Path, location: ArtifactLocation
) -> ArtifactInspection:
    """Inspect one locked path by metadata and receipt, never by payload digest."""
    try:
        status = path.stat()
    except (FileNotFoundError, NotADirectoryError):
        return ArtifactInspection(
            artifact.label, path, location, "absent", None, artifact.size_bytes
        )
    except OSError as error:
        raise EngineError(f"cannot inspect model artifact {path}: {error}") from error
    if status.st_size != artifact.size_bytes:
        state: ArtifactStatus = "wrong-size"
    else:
        identity = ArtifactIdentity(
            path.absolute(), status.st_size, status.st_mtime_ns, artifact.remote.sha256
        )
        state = "receipt-verified" if is_verified(identity) else "present-unverified"
    return ArtifactInspection(
        artifact.label, path, location, state, status.st_size, artifact.size_bytes
    )


def _inspect_custom(config: Config) -> ModelInspection:
    """Describe one user-managed path without applying the locked default-model contract."""
    if config.model_path is None:
        diagnostic = "custom model requires an explicit model_path"
        return ModelInspection(config.model, False, (), (diagnostic,))
    path = config.model_path
    try:
        size = path.stat().st_size
        status: ArtifactStatus = "present-unverified"
    except (FileNotFoundError, NotADirectoryError):
        size, status = None, "absent"
    except OSError as error:
        raise EngineError(f"cannot inspect custom model {path}: {error}") from error
    artifact = ArtifactInspection("custom model", path, "user-managed", status, size, None)
    return ModelInspection(config.model, False, (artifact,))


def inspect_model(config: Config, lock: JsonObject) -> ModelInspection:
    """Inspect default copies or one custom path without downloads, hashes, or writes."""
    default_model = cast(str, lock["default_model"])
    if config.model_path is not None or config.model != default_model:
        return _inspect_custom(config)
    store = models_dir()
    snapshot = _snapshot_dir(lock)
    inspected: list[ArtifactInspection] = []
    for artifact in model_artifacts(lock):
        inspected.append(
            _inspect_artifact(artifact, store / artifact.remote.filename, "managed-store")
        )
        if snapshot is not None:
            path = snapshot / artifact.remote.filename
            inspected.append(_inspect_artifact(artifact, path, "hugging-face-cache"))
    return ModelInspection(config.model, True, tuple(inspected))


def remove_copy(copy: StoredArtifact, root: Path | None) -> None:
    """Delete one located copy, leaving behind nothing that `pull` had written for it.

    The receipt goes with the file it describes, because `pull` is what wrote it; the store
    directory goes once it is empty, because `pull` is what created it. What stays behind is only
    what this tool did not put there (D-078).
    """
    if not copy.is_shared_cache:
        _unlink(copy.path)
        _prune_store()
    else:
        if root is None:
            message = f"cannot confine a cache deletion without a repository root: {copy.path}"
            raise EngineError(message)
        remove_cache_file(copy.path, root)
    forget(copy.path.absolute())


def _prune_store() -> None:
    """Remove the managed store directory once it holds nothing."""
    store = models_dir()
    if store.is_symlink() or not store.is_dir():
        return
    with suppress(OSError):
        store.rmdir()


def _unlink(path: Path) -> None:
    """Remove one file from the managed store, reporting a refusal rather than a traceback."""
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise EngineError(f"cannot remove {path}: {error}") from error
