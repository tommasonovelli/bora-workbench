"""Tests for the managed model store: resolution order, acquisition, and confined removal."""

from __future__ import annotations

import pytest

from bora_workbench import engine, models
from bora_workbench._model_removal import remove_cache_file
from bora_workbench.config import Config
from bora_workbench.engine import ModelRequest
from tests.model_store_fixtures import (  # noqa: F401  (locations is a fixture)
    PROJECTOR,
    WEIGHTS,
    locations,
    tiny_lock,
)
from tests.symlink_support import require_symlinks


def place(directory, name: str, data: bytes):
    """Write one artifact into a location that may not exist yet."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    target.write_bytes(data)
    return target


def test_store_copy_is_preferred_over_the_pinned_snapshot(locations) -> None:  # noqa: F811
    """The store is the first place resolution looks, because it is the one the tool owns."""
    lock = tiny_lock()
    stored = place(locations.store, "model.gguf", WEIGHTS)
    place(locations.snapshot, "model.gguf", WEIGHTS)

    resolved = engine.resolve_model(Config(model="owner/model:file"), lock, ModelRequest())

    assert resolved.model_path == stored.resolve()


def test_pinned_snapshot_still_resolves_when_the_store_is_empty(locations) -> None:  # noqa: F811
    """Weights acquired before the store existed keep launching from the read-only fallback."""
    lock = tiny_lock()
    cached = place(locations.snapshot, "model.gguf", WEIGHTS)

    resolved = engine.resolve_model(Config(model="owner/model:file"), lock, ModelRequest())

    assert resolved.model_path == cached.resolve()


def test_ensure_artifact_downloads_only_what_the_store_is_missing(
    locations,  # noqa: F811
    monkeypatch,
) -> None:
    """A complete, correctly sized artifact is verified once and then never fetched again."""
    weights, projector = models.model_artifacts(tiny_lock())
    calls: list[str] = []

    def fake_download(asset, destination, progress=None):
        """Stand in for the network by writing the bytes the digest expects."""
        calls.append(asset.filename)
        return place(
            destination, asset.filename, WEIGHTS if "model" in asset.filename else PROJECTOR
        )

    monkeypatch.setattr(models, "download_file", fake_download)

    assert models.ensure_artifact(weights) is False
    assert models.ensure_artifact(projector) is False
    assert calls == ["model.gguf", "mmproj.gguf"]
    assert models.ensure_artifact(weights) is True
    assert calls == ["model.gguf", "mmproj.gguf"]


def test_locate_copies_separates_the_store_from_the_shared_cache(locations) -> None:  # noqa: F811
    """Every existing copy is reported, and only the cache ones are marked as shared."""
    lock = tiny_lock()
    place(locations.store, "model.gguf", WEIGHTS)
    place(locations.snapshot, "model.gguf", WEIGHTS)
    place(locations.snapshot, "mmproj.gguf", PROJECTOR)

    copies = models.locate_copies(lock)

    assert [copy.is_shared_cache for copy in copies] == [False, True, True]
    assert sum(copy.size_bytes for copy in copies) == 2 * len(WEIGHTS) + len(PROJECTOR)


def test_cache_removal_refuses_a_path_outside_the_pinned_snapshot(locations) -> None:  # noqa: F811
    """Confinement is checked before anything is unlinked, not after."""
    stray = place(locations.repository, "loose.gguf", WEIGHTS)

    with pytest.raises(engine.EngineError, match="outside the pinned snapshot"):
        remove_cache_file(stray, locations.repository)

    assert stray.exists()


def test_cache_removal_deletes_a_plain_file_and_prunes_what_it_empties(
    locations,  # noqa: F811
) -> None:
    """The Windows layout stores real files, so removal must work with no blob at all."""
    cached = place(locations.snapshot, "model.gguf", WEIGHTS)
    (locations.repository / "blobs").mkdir(parents=True)

    remove_cache_file(cached, locations.repository)

    assert not cached.exists()
    assert not locations.repository.exists()


def test_cache_removal_keeps_a_repository_that_still_holds_something(
    locations,  # noqa: F811
) -> None:
    """Pruning uses rmdir, so a directory with any remaining content survives untouched."""
    cached = place(locations.snapshot, "model.gguf", WEIGHTS)
    kept = place(locations.repository / "refs", "main", b"a" * 40)

    remove_cache_file(cached, locations.repository)

    assert not cached.exists()
    assert kept.exists()


def test_cache_removal_frees_a_blob_no_other_snapshot_references(
    locations,  # noqa: F811
    tmp_path,
) -> None:
    """The canonical layout links snapshots at blobs, which must be collected when unused."""
    require_symlinks(tmp_path)
    blob = place(locations.repository / "blobs", "digest", WEIGHTS)
    locations.snapshot.mkdir(parents=True)
    link = locations.snapshot / "model.gguf"
    link.symlink_to(blob)

    remove_cache_file(link, locations.repository)

    assert not link.exists()
    assert not blob.exists()


def test_cache_removal_keeps_a_blob_another_snapshot_still_uses(
    locations,  # noqa: F811
    tmp_path,
) -> None:
    """A second revision sharing the same content must survive the deletion of the first."""
    require_symlinks(tmp_path)
    blob = place(locations.repository / "blobs", "digest", WEIGHTS)
    locations.snapshot.mkdir(parents=True)
    link = locations.snapshot / "model.gguf"
    link.symlink_to(blob)
    other = locations.repository / "snapshots" / ("b" * 40)
    other.mkdir(parents=True)
    (other / "model.gguf").symlink_to(blob)

    remove_cache_file(link, locations.repository)

    assert not link.exists()
    assert blob.exists()


def test_cache_removal_refuses_a_link_that_leaves_the_repository(
    locations,  # noqa: F811
    tmp_path,
) -> None:
    """A poisoned snapshot entry may not be followed to a file outside its own blobs."""
    require_symlinks(tmp_path)
    outside = place(tmp_path / "elsewhere", "victim.bin", WEIGHTS)
    locations.snapshot.mkdir(parents=True)
    link = locations.snapshot / "model.gguf"
    link.symlink_to(outside)

    with pytest.raises(engine.EngineError, match="outside its blobs"):
        remove_cache_file(link, locations.repository)

    assert outside.exists()
