"""Uninstall CLI tests for preview, confirmation, confinement, and idempotence (Step 6A)."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import qwen_launcher._cli_uninstall as uninstall_cli
import qwen_launcher._uninstall as uninstall_module
from qwen_launcher.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def patch_empty_service_status(monkeypatch) -> None:
    """Keep uninstall tests isolated from the host process-state directory."""
    empty = SimpleNamespace(services=(), warnings=())
    monkeypatch.setattr(uninstall_cli, "status_services", lambda: empty)


def patch_managed_roots(tmp_path, monkeypatch) -> dict[str, Path]:
    """Redirect the four managed roots into one isolated test tree.

    The `_uninstall` module binds the path helpers at import time, so each lookup is patched on that
    module directly, mirroring how the record module is patched elsewhere.
    """
    roots = {
        "config_dir": tmp_path / "config" / "qwen-launcher",
        "data_dir": tmp_path / "data" / "qwen-launcher",
        "cache_dir": tmp_path / "cache" / "qwen-launcher",
        "state_dir": tmp_path / "state" / "qwen-launcher",
    }
    for name, path in roots.items():
        monkeypatch.setattr(uninstall_module, name, lambda path=path: path)
    return roots


def populate(roots: dict[str, Path]) -> None:
    """Create each managed root with one nested file so deletion is observable."""
    for path in roots.values():
        path.mkdir(parents=True)
        (path / "content.txt").write_text("managed", encoding="utf-8")


def test_uninstall_cancellation_preserves_every_root(tmp_path, monkeypatch) -> None:
    """Declining the confirmation deletes nothing and still reminds about uv removal."""
    roots = patch_managed_roots(tmp_path, monkeypatch)
    populate(roots)

    result = runner.invoke(app, ["uninstall"], input="n\n")

    assert result.exit_code == 0
    assert "cancelled" in result.stdout
    assert all(path.exists() for path in roots.values())
    assert "uv tool uninstall qwen-launcher" in result.stdout


def test_uninstall_removes_only_managed_roots_and_spares_hugging_face_cache(
    tmp_path, monkeypatch
) -> None:
    """Confirmed uninstall deletes the four roots while leaving an external cache untouched."""
    roots = patch_managed_roots(tmp_path, monkeypatch)
    populate(roots)
    hugging_face_cache = tmp_path / "huggingface" / "hub"
    hugging_face_cache.mkdir(parents=True)
    (hugging_face_cache / "model.gguf").write_text("weights", encoding="utf-8")

    result = runner.invoke(app, ["uninstall"], input="y\n")

    assert result.exit_code == 0
    assert "The Hugging Face cache is never touched." in result.stdout
    assert not any(path.exists() for path in roots.values())
    assert (hugging_face_cache / "model.gguf").read_text(encoding="utf-8") == "weights"
    assert "uv tool uninstall qwen-launcher" in result.stdout


def test_uninstall_is_idempotent_when_roots_are_absent(tmp_path, monkeypatch) -> None:
    """Absent roots produce a clean report, no prompt, and no created directories."""
    roots = patch_managed_roots(tmp_path, monkeypatch)

    result = runner.invoke(app, ["uninstall"])

    assert result.exit_code == 0
    assert "nothing to remove" in result.stdout
    assert not any(path.exists() for path in roots.values())
    assert not list(tmp_path.iterdir())


def test_uninstall_reports_partially_absent_roots(tmp_path, monkeypatch) -> None:
    """A mix of present and absent roots removes the present ones and reports the rest absent."""
    roots = patch_managed_roots(tmp_path, monkeypatch)
    roots["data_dir"].mkdir(parents=True)
    (roots["data_dir"] / "record.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["uninstall"], input="y\n")

    assert result.exit_code == 0
    assert f"Removed: {roots['data_dir']}" in result.stdout
    assert f"Already absent: {roots['config_dir']}" in result.stdout
    assert not roots["data_dir"].exists()


def test_removal_rejects_a_root_outside_the_public_set(tmp_path, monkeypatch) -> None:
    """A tampered deletion set is refused before an unlisted directory can be removed."""
    patch_managed_roots(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    roots = (uninstall_module.ManagedRoot("data", outside, True),)

    with pytest.raises(uninstall_module.UninstallError, match="root set changed"):
        uninstall_module.remove_managed_roots(roots)

    assert outside.exists()


def test_removal_preserves_a_root_created_after_preview(tmp_path, monkeypatch) -> None:
    """A directory absent from the confirmed preview is not deleted if it appears later."""
    paths = patch_managed_roots(tmp_path, monkeypatch)
    preview = uninstall_module.managed_roots()
    paths["data_dir"].mkdir(parents=True)

    report = uninstall_module.remove_managed_roots(preview)

    assert paths["data_dir"].exists()
    assert paths["data_dir"] in report.absent


def test_uninstall_refuses_to_orphan_a_running_service(tmp_path, monkeypatch) -> None:
    """A live managed service must be stopped before its state can be deleted."""
    roots = patch_managed_roots(tmp_path, monkeypatch)
    populate(roots)
    running = SimpleNamespace(services=(SimpleNamespace(label="llama-server"),), warnings=())
    monkeypatch.setattr(uninstall_cli, "status_services", lambda: running)

    result = runner.invoke(app, ["uninstall"])

    assert result.exit_code == 1
    assert "qwen-launcher stop" in result.stderr
    assert all(path.exists() for path in roots.values())


def test_uninstall_maps_removal_failure_to_exit_1(tmp_path, monkeypatch) -> None:
    """An actionable removal failure exits with code 1 and prints to stderr without a traceback."""
    roots = patch_managed_roots(tmp_path, monkeypatch)
    populate(roots)

    def fail(_roots):
        """Simulate an expected locked-directory removal failure."""
        raise uninstall_module.UninstallError("could not remove locked directory")

    monkeypatch.setattr(uninstall_cli, "remove_managed_roots", fail)

    result = runner.invoke(app, ["uninstall"], input="y\n")

    assert result.exit_code == 1
    assert "Uninstall error" in result.stderr
    assert "locked directory" in result.stderr
    assert "Traceback" not in result.stderr
