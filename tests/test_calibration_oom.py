"""Offline tests for reading out-of-memory evidence out of engine logs."""

from __future__ import annotations

from pathlib import Path

import pytest

from qwen_launcher._calibration_oom import oom_resource, read_logs

_CUDA_FAILURE = (
    "ggml_backend_cuda_buffer_type_alloc_buffer: allocating 11807.70 MiB on device 0: "
    "cudaMalloc failed: out of memory\n"
    "llama_model_load: error loading model: unable to allocate CUDA0 buffer\n"
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (_CUDA_FAILURE, "vram"),
        ("ggml_backend_cpu_buffer_type_alloc_buffer: out of memory", "ram"),
        ("srv load_model: OOM while preparing the host buffer", "ram"),
        ("srv init: renderer zoom failure", None),
        ("srv init: model loaded", None),
        ("", None),
    ],
)
def test_oom_resource_names_only_the_failing_device(text: str, expected: str | None) -> None:
    """Name the exhausted resource from the failing line, never from unrelated log context."""
    assert oom_resource(text) == expected


def test_device_marker_is_read_per_line_not_per_log() -> None:
    """Keep a CUDA banner elsewhere from turning a host allocation failure into a GPU one."""
    log = "ggml_cuda_init: found 1 CUDA device\nfailed to allocate host buffer: out of memory\n"
    assert oom_resource(log) == "ram"


def test_read_logs_skips_unreadable_paths(tmp_path: Path) -> None:
    """Concatenate the logs this run can open and ignore the ones it cannot."""
    present = tmp_path / "server.log"
    present.write_text("out of memory on device 0\n", encoding="utf-8")
    text = read_logs((present, tmp_path / "missing.log"))
    assert oom_resource(text) == "vram"
