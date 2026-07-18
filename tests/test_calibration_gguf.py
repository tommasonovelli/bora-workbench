"""Offline tests for the GGUF metadata reader that predicts the axis domain."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from qwen_launcher._calibration_gguf import GgufError, read_block_count


def _string(value: str) -> bytes:
    """Encode one length-prefixed GGUF string."""
    data = value.encode("utf-8")
    return struct.pack("<Q", len(data)) + data


def _kv_string(key: str, value: str) -> bytes:
    """Encode one string metadata entry."""
    return _string(key) + struct.pack("<I", 8) + _string(value)


def _kv_u32(key: str, value: int) -> bytes:
    """Encode one uint32 metadata entry."""
    return _string(key) + struct.pack("<I", 4) + struct.pack("<I", value)


def _kv_f32(key: str, value: float) -> bytes:
    """Encode one float32 metadata entry."""
    return _string(key) + struct.pack("<I", 6) + struct.pack("<f", value)


def _kv_string_array(key: str, values: list[str]) -> bytes:
    """Encode one string-array metadata entry that must be skipped element by element."""
    payload = struct.pack("<I", 8) + struct.pack("<Q", len(values))
    return _string(key) + struct.pack("<I", 9) + payload + b"".join(_string(v) for v in values)


def write_gguf(path: Path, entries: list[bytes], version: int = 3) -> Path:
    """Write one synthetic GGUF header with zero tensors and the given metadata."""
    header = b"GGUF" + struct.pack("<I", version)
    header += struct.pack("<Q", 0) + struct.pack("<Q", len(entries))
    path.write_bytes(header + b"".join(entries))
    return path


def moe_entries(block_count: int = 41) -> list[bytes]:
    """Build the metadata the pinned qwen35moe artifact shape declares."""
    return [
        _kv_string("general.architecture", "qwen35moe"),
        _kv_u32("qwen35moe.block_count", block_count),
        _kv_u32("qwen35moe.expert_count", 256),
    ]


def test_block_count_is_read_while_skipping_unrelated_metadata(tmp_path) -> None:
    """Find the architecture-scoped block count between skippable strings and arrays."""
    entries = [
        _kv_string_array("tokenizer.ggml.tokens", ["a", "bb", "ccc"]),
        _kv_f32("general.some_scale", 1.5),
        *moe_entries(41),
        _kv_string("general.name", "synthetic"),
    ]
    path = write_gguf(tmp_path / "model.gguf", entries)

    assert read_block_count(path) == 41


@pytest.mark.parametrize("version", [2, 3])
def test_supported_gguf_versions_are_accepted(tmp_path, version) -> None:
    """Parse both header versions observed for published GGUF artifacts."""
    path = write_gguf(tmp_path / "model.gguf", moe_entries(12), version=version)

    assert read_block_count(path) == 12


def test_missing_architecture_is_actionable(tmp_path) -> None:
    """Reject metadata that never declares the architecture that scopes the domain."""
    path = write_gguf(tmp_path / "model.gguf", [_kv_u32("qwen35moe.block_count", 41)])

    with pytest.raises(GgufError, match=r"general\.architecture"):
        read_block_count(path)


def test_missing_block_count_is_actionable(tmp_path) -> None:
    """Reject metadata without the architecture's block count instead of guessing."""
    path = write_gguf(tmp_path / "model.gguf", [_kv_string("general.architecture", "qwen35moe")])

    with pytest.raises(GgufError, match="block_count"):
        read_block_count(path)


def test_non_gguf_and_truncated_files_are_rejected(tmp_path) -> None:
    """Diagnose a wrong magic and an incomplete header without tracebacks."""
    wrong = tmp_path / "wrong.gguf"
    wrong.write_bytes(b"NOTGGUF!")
    truncated = tmp_path / "short.gguf"
    truncated.write_bytes(b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", 0))

    with pytest.raises(GgufError, match="not a GGUF file"):
        read_block_count(wrong)
    with pytest.raises(GgufError, match="ended unexpectedly"):
        read_block_count(truncated)


def test_unsupported_version_is_rejected(tmp_path) -> None:
    """Refuse header versions the parser has not been verified against."""
    path = write_gguf(tmp_path / "model.gguf", moe_entries(), version=99)

    with pytest.raises(GgufError, match="version 99"):
        read_block_count(path)
