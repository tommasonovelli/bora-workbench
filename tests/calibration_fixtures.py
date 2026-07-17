"""Synthetic calibration policy builders shared by semantic validation tests."""

from __future__ import annotations


def valid_policy(backend: str = "cuda", engine: str = "b10011") -> dict[str, object]:
    """Build one complete synthetic policy without publishing calibration content."""
    candidate: dict[str, object] = {"id": "safe", "ctx": 8192}
    policy: dict[str, object] = {
        "id": "synthetic-policy",
        "model": "owner/model:file",
        "engine": engine,
        "backend": backend,
        "os": ["linux"],
        "stable_start_runs": 2,
        "modes": {"coding": {"candidates": [candidate]}},
        "hardware_classes": [
            {
                "id": "ram-32-vram-8",
                "ram_gib": [31, 33],
                "vram_gib": [7, 9] if backend == "cuda" else [0, None],
            }
        ],
    }
    if backend == "cuda":
        candidate["n_cpu_moe"] = 48
        policy["minimum_calibration_vram_gib"] = 8
        policy["minimum_free_vram_gib"] = 0.5
        policy["vram_release_tolerance_gib"] = 0.125
    return {
        "schema": "calibration-policy/v1",
        "benchmark_protocol": "benchmark/v1",
        "gpu_poll_interval_ms": 250,
        "gpu_release_stabilization_ms": 10000,
        "policies": [policy],
    }
