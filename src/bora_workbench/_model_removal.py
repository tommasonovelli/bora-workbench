"""Delete pinned model artifacts from the shared Hugging Face cache without leaving it (D-079).

The cache is not ours. Other tools on the same machine keep their own repositories beside ours, and
a snapshot entry may be a symlink into a content-addressed blob that a second revision of the same
repository still needs. So every deletion here is confined by construction rather than by care:

1. only a file directly inside `<repository>/snapshots/<revision>/` may be removed;
2. a symlinked entry is followed only as far as `<repository>/blobs/`, never outside it;
3. the blob is removed only once no other snapshot of that repository still points at it;
4. a symlinked cache directory is refused instead of followed;
5. directories are pruned with `rmdir`, which by definition cannot delete a directory that still
   holds anything;
6. the repository directory itself goes only when its last snapshot did, leaving no stub whose
   `refs` still name a revision this machine no longer has.

Writing into the cache stays forbidden: fabricating snapshots or refs is what would corrupt the
expectations of the tools that share it (specification section 5.12).
"""

from __future__ import annotations

import shutil
from contextlib import suppress
from pathlib import Path

from bora_workbench.engine import EngineError


def _require_confined(path: Path, repository: Path) -> None:
    """Refuse any path that is not a direct child of one pinned snapshot of this repository."""
    snapshots = repository / "snapshots"
    if path.parent.parent != snapshots:
        raise EngineError(f"refusing to delete outside the pinned snapshot: {path}")
    for directory in (repository, snapshots, path.parent):
        if directory.is_symlink():
            raise EngineError(f"refusing to follow a symlinked cache directory: {directory}")


def _owned_blob(path: Path, repository: Path) -> Path | None:
    """Return the blob a snapshot entry points at, refusing a link that leaves the repository.

    On Windows the cache usually stores real files instead of links, so the common case here is
    simply `None`; both layouts have to work because both exist on supported hosts.
    """
    if not path.is_symlink():
        return None
    blob = path.resolve()
    if not blob.is_relative_to((repository / "blobs").resolve()):
        raise EngineError(f"refusing to follow a cache link outside its blobs: {path}")
    return blob


def _is_referenced(blob: Path, repository: Path) -> bool:
    """Report whether another snapshot of the same repository still points at this blob."""
    return any(
        entry.is_symlink() and entry.resolve() == blob
        for entry in (repository / "snapshots").glob("*/*")
    )


def _unlink(path: Path) -> None:
    """Remove one cache file, reporting a refusal rather than a traceback."""
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise EngineError(f"cannot remove {path}: {error}") from error


def _remove_if_empty(directory: Path) -> None:
    """Remove one directory only when it is a real directory that holds nothing."""
    if directory.is_symlink() or not directory.is_dir():
        return
    with suppress(OSError):
        directory.rmdir()


def _holds_only_refs(repository: Path) -> bool:
    """Report whether nothing but the `refs` stub survives in the cached repository.

    Every other directory has already been removed by `rmdir` if it was empty, so anything still
    present besides `refs` is real content: another revision's snapshot, or blobs a file this tool
    does not manage still needs.
    """
    return all(entry.name == "refs" for entry in repository.iterdir())


def _prune_repository(repository: Path) -> None:
    """Remove the cached repository once its last snapshot is gone.

    What `refs` names is a revision whose files no longer exist, so leaving it behind is leaving a
    stub that claims a cached model this machine no longer has. Removing it stays confined: the
    directory belongs to the locked repository, and a surviving snapshot or blob stops the prune.
    """
    if repository.is_symlink() or not repository.is_dir():
        return
    with suppress(OSError):
        if _holds_only_refs(repository):
            shutil.rmtree(repository)


def remove_cache_file(path: Path, repository: Path) -> None:
    """Delete one pinned artifact from the cache, then prune whatever it left empty.

    The link is removed before the blob is checked for other references, so the entry being
    deleted cannot count as a reason to keep its own content.
    """
    _require_confined(path, repository)
    blob = _owned_blob(path, repository)
    _unlink(path)
    if blob is not None and not _is_referenced(blob, repository):
        _unlink(blob)
    for directory in (path.parent, repository / "snapshots", repository / "blobs"):
        _remove_if_empty(directory)
    _prune_repository(repository)
