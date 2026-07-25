import hashlib

import pytest

from bora_workbench.resources import read_json, read_text, resource_as_file


def test_read_packaged_resource():
    text = read_text("README.txt")
    assert "Spike 0" in text


def test_resource_can_be_materialized_temporarily():
    with resource_as_file("README.txt") as path:
        assert path.is_file()
        assert path.read_text(encoding="utf-8").startswith("Package resources")


def test_engine_lock_is_packaged():
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


@pytest.mark.parametrize("path", ["../README.md", "/tmp/file", r"C:\\tmp\\file"])
def test_resource_rejects_unsafe_path(path):
    with pytest.raises(ValueError):
        read_text(path)
