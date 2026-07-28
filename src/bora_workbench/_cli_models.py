"""Present the commands that acquire and release the pinned model weights.

`pull` fetches the artifacts named by `engine.lock` into the managed store and proves them against
their locked digests; `rm` gives the disk space back. They are presentation only: the store, the
transfer, and the confined cache deletion all live in `models.py` (specification section 4.1).

Deleting is split into two questions on purpose. The store belongs to this tool, while the Hugging
Face cache is shared with everything else on the machine, so consenting to the first never implies
consenting to the second (D-079).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from bora_workbench._cli_theme import (
    format_bytes,
    print_error,
    print_heading,
    print_note,
    print_success,
    print_warning,
    transferring,
)
from bora_workbench.engine import EngineError, JsonObject, load_engine_lock
from bora_workbench.models import (
    ModelArtifact,
    StoredArtifact,
    display_name,
    ensure_artifact,
    locate_copies,
    model_artifacts,
    remove_copy,
    repository_root,
)
from bora_workbench.paths import models_dir


@dataclass(frozen=True, slots=True)
class RemoveOptions:
    """Group what `rm` was asked to spare and whether it may delete at all."""

    keep_cache: bool
    dry_run: bool


@dataclass(frozen=True, slots=True)
class _Group:
    """Pair one confirmable set of copies with the heading and question that describe it."""

    title: str
    question: str
    copies: tuple[StoredArtifact, ...]


def _pull_one(artifact: ModelArtifact, stdout: Console) -> None:
    """Fetch one artifact with visible byte progress and say what the store already held."""
    with transferring(stdout, f"Downloading {artifact.label}") as progress:
        was_present = ensure_artifact(artifact, progress)
    state = "already present and verified" if was_present else "downloaded and verified"
    print_note(stdout, artifact.label, f"{format_bytes(artifact.size_bytes)} {state}")


def pull_model(lock: JsonObject, stdout: Console) -> None:
    """Leave every pinned artifact verified in the managed store, downloading what is missing.

    Shared with `engine install`, which acquires the weights in the same call that provisions the
    engine so that a first run needs one command instead of three (D-078).
    """
    artifacts = model_artifacts(lock)
    print_note(stdout, "Model", display_name(lock))
    print_note(stdout, "Store", str(models_dir()))
    print_note(stdout, "Total size", format_bytes(sum(item.size_bytes for item in artifacts)))
    for artifact in artifacts:
        _pull_one(artifact, stdout)


def run_pull(stdout: Console, stderr: Console) -> None:
    """Download the pinned model into the managed store and map failures to exit code 1."""
    try:
        lock = load_engine_lock()
        pull_model(lock, stdout)
    except EngineError as error:
        print_error(stderr, "Model error", str(error))
        raise typer.Exit(code=1) from error
    except KeyboardInterrupt as error:
        print_warning(stderr, "Download interrupted; nothing incomplete was kept.")
        raise typer.Exit(code=130) from error
    print_success(stdout, "Model ready", display_name(lock))


def _cache_group(copies: tuple[StoredArtifact, ...]) -> _Group:
    """Build the shared-cache question, whose heading has to name why it is asked separately."""
    title = "In the Hugging Face cache, which is shared with other tools on this machine"
    return _Group(title, "Also delete them from the shared Hugging Face cache?", copies)


def _groups(copies: tuple[StoredArtifact, ...], keep_cache: bool) -> tuple[_Group, ...]:
    """Split located copies into the managed store and the shared cache, in that order."""
    store = tuple(copy for copy in copies if not copy.is_shared_cache)
    cache = () if keep_cache else tuple(copy for copy in copies if copy.is_shared_cache)
    groups = []
    if store:
        title = "In the bora-workbench model store"
        groups.append(_Group(title, "Delete them from the model store?", store))
    if cache:
        groups.append(_cache_group(cache))
    return tuple(groups)


def _show_group(group: _Group, stdout: Console) -> None:
    """List exactly which files a confirmation would delete, and how much it would free."""
    freed = sum(copy.size_bytes for copy in group.copies)
    for copy in group.copies:
        size = format_bytes(copy.size_bytes)
        stdout.print(f"  {copy.path} ({size})", markup=False, soft_wrap=True)
    print_note(stdout, "Frees", format_bytes(freed))


def _remove_group(group: _Group, root: Path | None, stdout: Console) -> int:
    """Ask one question, then delete only that group, and report the bytes it freed."""
    print_heading(stdout, group.title)
    _show_group(group, stdout)
    if not typer.confirm(group.question, default=False):
        stdout.print("Skipped; those files were left in place.")
        return 0
    freed = 0
    for copy in group.copies:
        remove_copy(copy, root)
        stdout.print(f"Removed: {copy.path}", markup=False, soft_wrap=True)
        freed += copy.size_bytes
    return freed


def _delete(options: RemoveOptions, lock: JsonObject, stdout: Console) -> None:
    """Show the plan, then delete each confirmed group unless this is only a dry run."""
    groups = _groups(locate_copies(lock), options.keep_cache)
    if not groups:
        stdout.print("No pinned model artifacts are present; nothing to remove.")
        return
    if options.dry_run:
        for group in groups:
            print_heading(stdout, group.title)
            _show_group(group, stdout)
        print_note(stdout, "Dry run", "nothing was deleted")
        return
    root = repository_root(lock)
    freed = sum(_remove_group(group, root, stdout) for group in groups)
    print_success(stdout, "Removed", f"{format_bytes(freed)} freed")


def offer_cache_removal(lock: JsonObject, stdout: Console) -> None:
    """Ask the shared-cache question on its own and delete only what it authorizes.

    `uninstall` takes the model store with the data root it already owns, but weights that live in
    the shared Hugging Face cache would survive it. They are offered here as an explicitly separate
    request rather than folded into the single uninstall confirmation (D-079).
    """
    copies = tuple(copy for copy in locate_copies(lock) if copy.is_shared_cache)
    if not copies:
        return
    freed = _remove_group(_cache_group(copies), repository_root(lock), stdout)
    if freed:
        print_success(stdout, "Removed", f"{format_bytes(freed)} freed")


def run_remove_model(options: RemoveOptions, stdout: Console, stderr: Console) -> None:
    """Delete the pinned model from the store, and from the shared cache when confirmed."""
    try:
        _delete(options, load_engine_lock(), stdout)
    except EngineError as error:
        print_error(stderr, "Model error", str(error))
        raise typer.Exit(code=1) from error
    except (KeyboardInterrupt, typer.Abort) as error:
        print_warning(stderr, f"Removal cancelled: {error}")
        raise typer.Exit(code=130) from error
