"""Tests for `bora pull` and `bora rm`: what they show, what they ask, and what they delete."""

from __future__ import annotations

from typer.testing import CliRunner

import bora_workbench._cli_models as models_cli
from bora_workbench import models
from bora_workbench.cli import app
from tests.model_store_fixtures import (  # noqa: F401  (locations is a fixture)
    PROJECTOR,
    WEIGHTS,
    locations,
    tiny_lock,
)

runner = CliRunner()


def place(directory, name: str, data: bytes):
    """Write one artifact into a location that may not exist yet."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    target.write_bytes(data)
    return target


def use_tiny_lock(monkeypatch) -> None:
    """Give both command modules the small pinned identity the fixtures build."""
    monkeypatch.setattr(models_cli, "load_engine_lock", tiny_lock)


def populate(locations) -> None:  # noqa: F811
    """Put one copy of every pinned artifact in the store and in the shared cache."""
    place(locations.store, "model.gguf", WEIGHTS)
    place(locations.store, "mmproj.gguf", PROJECTOR)
    place(locations.snapshot, "model.gguf", WEIGHTS)
    place(locations.snapshot, "mmproj.gguf", PROJECTOR)


def test_pull_downloads_into_the_store_and_reports_each_artifact(
    locations,  # noqa: F811
    monkeypatch,
) -> None:
    """`pull` names the model, the destination, and what each artifact cost."""
    use_tiny_lock(monkeypatch)
    monkeypatch.setattr(
        models,
        "download_file",
        lambda asset, destination, progress=None: place(
            destination, asset.filename, WEIGHTS if "model" in asset.filename else PROJECTOR
        ),
    )

    result = runner.invoke(app, ["pull"])

    assert result.exit_code == 0
    assert (locations.store / "model.gguf").read_bytes() == WEIGHTS
    assert (locations.store / "mmproj.gguf").read_bytes() == PROJECTOR
    assert "Qwen 3.6" in result.stdout
    assert "downloaded and verified" in result.stdout


def test_rm_dry_run_lists_every_copy_and_deletes_nothing(
    locations,  # noqa: F811
    monkeypatch,
) -> None:
    """A dry run is the way to see the plan without being asked anything."""
    use_tiny_lock(monkeypatch)
    populate(locations)

    result = runner.invoke(app, ["rm", "--dry-run"])

    assert result.exit_code == 0
    assert "nothing was deleted" in result.stdout
    assert "shared with other tools" in result.stdout
    assert "?" not in result.stdout
    assert (locations.store / "model.gguf").exists()
    assert (locations.snapshot / "model.gguf").exists()


def test_rm_keeps_the_shared_cache_when_asked_to(
    locations,  # noqa: F811
    monkeypatch,
) -> None:
    """`--keep-hf` removes the store copies and never raises the second question."""
    use_tiny_lock(monkeypatch)
    populate(locations)

    result = runner.invoke(app, ["rm", "--keep-hf"], input="y\n")

    assert result.exit_code == 0
    assert not (locations.store / "model.gguf").exists()
    assert (locations.snapshot / "model.gguf").exists()
    assert "Hugging Face" not in result.stdout


def test_rm_asks_separately_before_touching_the_shared_cache(
    locations,  # noqa: F811
    monkeypatch,
) -> None:
    """Consenting to the store must not consent to the cache: the second answer decides it."""
    use_tiny_lock(monkeypatch)
    populate(locations)

    result = runner.invoke(app, ["rm"], input="y\nn\n")

    assert result.exit_code == 0
    assert not (locations.store / "model.gguf").exists()
    assert (locations.snapshot / "model.gguf").exists()
    assert "shared with other tools" in result.stdout


def test_rm_deletes_both_locations_when_both_are_confirmed(
    locations,  # noqa: F811
    monkeypatch,
) -> None:
    """Two explicit answers delete both copies and the emptied cache directories."""
    use_tiny_lock(monkeypatch)
    populate(locations)

    result = runner.invoke(app, ["rm"], input="y\ny\n")

    assert result.exit_code == 0
    assert not (locations.store / "model.gguf").exists()
    assert not locations.repository.exists()


def test_rm_reports_an_empty_machine_without_asking(
    locations,  # noqa: F811
    monkeypatch,
) -> None:
    """Nothing present means nothing to confirm and nothing to delete."""
    use_tiny_lock(monkeypatch)

    result = runner.invoke(app, ["rm"])

    assert result.exit_code == 0
    assert "nothing to remove" in result.stdout
