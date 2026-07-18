"""Read the pinned model's MoE block count from its GGUF metadata.

calibration/v2 predicts the legal ``n_cpu_moe`` domain as ``[0, block_count]`` from the artifact's
own metadata instead of remembered candidate lists (D-039; design document section 2.1). Only the
header is parsed sequentially; tensor data is never read, so the multi-GiB file stays untouched.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO

_MAGIC = b"GGUF"
_SUPPORTED_VERSIONS = (2, 3)
_STRING_TYPE = 8
_ARRAY_TYPE = 9
_SIMPLE_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_INTEGER_FORMATS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 10: "<Q", 11: "<q"}
_MAX_KEY_BYTES = 65_536
_MAX_METADATA_ENTRIES = 1_048_576


class GgufError(RuntimeError):
    """Report a GGUF artifact whose metadata cannot provide the calibration domain."""


def _read_exact(source: BinaryIO, size: int) -> bytes:
    """Read exactly ``size`` bytes or diagnose a truncated header."""
    data = source.read(size)
    if len(data) != size:
        raise GgufError("GGUF metadata ended unexpectedly")
    return data


def _read_unsigned(source: BinaryIO, format_string: str) -> int:
    """Read one little-endian unsigned integer of the given struct format."""
    return int(struct.unpack(format_string, _read_exact(source, struct.calcsize(format_string)))[0])


def _read_string(source: BinaryIO, maximum_bytes: int | None = None) -> str:
    """Read one length-prefixed UTF-8 string, optionally bounding hostile lengths."""
    length = _read_unsigned(source, "<Q")
    if maximum_bytes is not None and length > maximum_bytes:
        raise GgufError("GGUF metadata key exceeds the supported length")
    try:
        return _read_exact(source, length).decode("utf-8")
    except UnicodeDecodeError as error:
        raise GgufError("GGUF metadata contains a non-UTF-8 string") from error


def _skip_string(source: BinaryIO) -> None:
    """Skip one length-prefixed string without reading its bytes into memory."""
    length = _read_unsigned(source, "<Q")
    source.seek(length, 1)


def _skip_value(source: BinaryIO, value_type: int) -> None:
    """Skip one metadata value of any GGUF type, recursing only for nested arrays."""
    if value_type in _SIMPLE_SIZES:
        source.seek(_SIMPLE_SIZES[value_type], 1)
        return
    if value_type == _STRING_TYPE:
        _skip_string(source)
        return
    if value_type != _ARRAY_TYPE:
        raise GgufError(f"GGUF metadata uses unknown value type {value_type}")
    element_type = _read_unsigned(source, "<I")
    count = _read_unsigned(source, "<Q")
    if element_type in _SIMPLE_SIZES:
        source.seek(_SIMPLE_SIZES[element_type] * count, 1)
        return
    for _ in range(count):
        _skip_value(source, element_type)


def _read_header(source: BinaryIO) -> int:
    """Validate magic and version, skip the tensor count, and return the metadata count."""
    if _read_exact(source, 4) != _MAGIC:
        raise GgufError("model artifact is not a GGUF file")
    version = _read_unsigned(source, "<I")
    if version not in _SUPPORTED_VERSIONS:
        raise GgufError(f"unsupported GGUF version {version}")
    _read_unsigned(source, "<Q")
    count = _read_unsigned(source, "<Q")
    if count > _MAX_METADATA_ENTRIES:
        raise GgufError("GGUF metadata entry count is implausibly large")
    return count


def _collect_metadata(source: BinaryIO) -> dict[str, object]:
    """Collect only the architecture and block-count keys, skipping every other value."""
    collected: dict[str, object] = {}
    for _ in range(_read_header(source)):
        key = _read_string(source, _MAX_KEY_BYTES)
        value_type = _read_unsigned(source, "<I")
        if key == "general.architecture" and value_type == _STRING_TYPE:
            collected[key] = _read_string(source, _MAX_KEY_BYTES)
        elif key.endswith(".block_count") and value_type in _INTEGER_FORMATS:
            collected[key] = _read_unsigned(source, _INTEGER_FORMATS[value_type])
        else:
            _skip_value(source, value_type)
    return collected


def read_block_count(model_path: Path) -> int:
    """Return the architecture-declared block count that bounds the ``n_cpu_moe`` domain."""
    try:
        with model_path.open("rb") as source:
            collected = _collect_metadata(source)
    except OSError as error:
        raise GgufError(f"cannot read GGUF metadata from {model_path}: {error}") from error
    except (struct.error, RecursionError) as error:
        raise GgufError(f"malformed GGUF metadata in {model_path}") from error
    architecture = collected.get("general.architecture")
    if not isinstance(architecture, str) or not architecture:
        raise GgufError("GGUF metadata does not declare general.architecture")
    block_count = collected.get(f"{architecture}.block_count")
    if not isinstance(block_count, int) or block_count < 1:
        raise GgufError(f"GGUF metadata does not declare a positive {architecture}.block_count")
    return block_count
