"""Tests for Traversable-based packaged resource access and path confinement."""

import hashlib

import pytest

from bora_workbench.resources import read_json, read_text, resource_as_file


def test_read_packaged_resource():
    """Read a packaged text resource without assuming it is a physical file."""
    text = read_text("README.txt")
    assert "Spike 0" in text


def test_resource_can_be_materialized_temporarily():
    """Expose a real path only for the lifetime of the `as_file()` context manager."""
    with resource_as_file("README.txt") as path:
        assert path.is_file()
        assert path.read_text(encoding="utf-8").startswith("Package resources")


def test_engine_lock_is_packaged():
    """Ship the pinned engine lock with its exact release, commit, and asset set."""
    lock = read_json("engine.lock")

    assert lock["schema"] == "engine-lock/v1"
    assert lock["release"] == "b10011"
    assert lock["source_commit"] == "bf2c86ddc0685f580595954056c2e77ebabfab4f"
    assert lock["assets_complete"] is True
    assert len(lock["assets"]) == 5


def test_managed_engine_notices_match_spike_evidence():
    """Ship exact llama.cpp and NVIDIA notices required by the verified asset terms."""
    expected = {
        "notices/llama.cpp-LICENSE": (
            "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d"
        ),
        "notices/NVIDIA-CUDA-EULA.html": (
            "6180cc2a02db890cf87ba52f078b7a222b04dcb3c2650865763d4f32ad663a5c"
        ),
    }
    for name, digest in expected.items():
        assert hashlib.sha256(read_text(name).encode()).hexdigest() == digest


def test_the_open_webui_licence_is_shipped_verbatim():
    """Carry the upstream licence of the interface bora starts, read at tag `v0.11.0`."""
    notice = read_text("notices/open-webui-LICENSE")

    assert (
        hashlib.sha256(notice.encode()).hexdigest()
        == "5f1bd74c48bf13ab0f82e177ad9e637313b92533d20ead2593d49347a47fc232"
    )
    # Clause 4 is the reason `WEBUI_NAME` is never set: the interface keeps its own name.
    assert 'from altering, removing, obscuring, or replacing any "Open WebUI"' in notice


@pytest.mark.parametrize("path", ["../README.md", "/tmp/file", r"C:\\tmp\\file"])
def test_resource_rejects_unsafe_path(path):
    """Refuse absolute, drive-relative, and parent-relative names before joining them."""
    with pytest.raises(ValueError):
        read_text(path)
