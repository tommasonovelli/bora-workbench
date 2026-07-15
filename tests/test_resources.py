import pytest

from qwen_launcher.resources import read_json, read_text, resource_as_file


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
    assert lock["assets_complete"] is False


@pytest.mark.parametrize("path", ["../README.md", "/tmp/file", r"C:\\tmp\\file"])
def test_resource_rejects_unsafe_path(path):
    with pytest.raises(ValueError):
        read_text(path)
