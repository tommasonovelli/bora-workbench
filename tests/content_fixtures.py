"""Synthetic content builders used only by Step 2B validation tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from qwen_launcher.resources import resource
from tests.calibration_fixtures import valid_policy

_ENGINE_COMMIT = "bf2c86ddc0685f580595954056c2e77ebabfab4f"


@dataclass(frozen=True, slots=True)
class ContentFiles:
    """Point to a synthetic resource root and its linked report/profile files."""

    root: Path
    report: Path
    profile: Path


def write_json(path: Path, value: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON for digest-sensitive fixtures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    """Read one synthetic JSON object."""
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_resource(root: Path, relative_path: str) -> None:
    """Copy one packaged resource through Traversable-safe bytes access."""
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(resource(relative_path).read_bytes())


def copy_resource_root(tmp_path: Path) -> Path:
    """Create a complete resource root with schemas, lock, and production modes only."""
    root = tmp_path / "resources"
    paths = [
        "engine.lock",
        "schemas/mode.v1.json",
        "schemas/profile.v1.json",
        "schemas/calibration-policy.v1.json",
        "schemas/calibration-report.v1.json",
        "schemas/calibration-record.v2.json",
        "content/modes/coding.json",
        "content/modes/studio.json",
        "content/modes/vstudio.json",
    ]
    for relative_path in paths:
        _copy_resource(root, relative_path)
    return root


def _candidate(backend: str) -> dict[str, object]:
    """Build one valid report candidate for the selected backend."""
    candidate: dict[str, object] = {
        "id": "safe",
        "ctx": 8192,
        "outcome": "valid",
        "successful_start_runs": 2,
        "vram_baseline_gib": 1 if backend == "cuda" else None,
        "vram_peak_gib": 7 if backend == "cuda" else None,
        "vram_min_free_gib": 1 if backend == "cuda" else None,
        "vram_release_used_gib": 1 if backend == "cuda" else None,
        "warmup_tok_s": 1,
        "measured_tok_s": [1, 2, 3, 4, 5],
        "tok_s": {"min": 1, "median": 3, "max": 5},
        "log_digests": [{"path": "logs/safe.log", "sha256": "0" * 64}],
    }
    if backend == "cuda":
        candidate["n_cpu_moe"] = 48
    return candidate


def _hardware(backend: str) -> dict[str, object]:
    """Build the CPU or CUDA hardware snapshot shared by synthetic reports."""
    is_cuda = backend == "cuda"
    return {
        "os_name": "linux",
        "os_version": "test",
        "cpu_name": "Test CPU",
        "cpu_cores": 12,
        "ram_total_gib": 32,
        "ram_available_gib": 24,
        "backend": backend,
        "gpu_index": 0 if is_cuda else None,
        "gpu_name": "Test GPU" if is_cuda else None,
        "gpu_driver": "test" if is_cuda else None,
        "vram_total_gib": 8 if is_cuda else None,
        "vram_free_gib": 7 if is_cuda else None,
    }


def valid_report(backend: str = "cuda", engine: str = "b10011") -> dict[str, object]:
    """Build one accepted, internally coherent calibration report."""
    candidate = _candidate(backend)
    policy_candidate = {"mode": "coding", "id": "safe", "ctx": 8192}
    if backend == "cuda":
        policy_candidate["n_cpu_moe"] = 48
    return {
        "schema": "calibration-report/v1",
        "id": "synthetic-report",
        "created_at": "2026-07-15T12:00:00Z",
        "decision": "accepted",
        "launcher_version": "0.1.0.dev0",
        "model": "owner/model:file",
        "engine": engine,
        "engine_source_commit": _ENGINE_COMMIT,
        "calibration_protocol": "calibration/v1",
        "benchmark_protocol": "benchmark/v1",
        "policy": {
            "id": "synthetic-policy",
            "gpu_poll_interval_ms": 250,
            "gpu_release_stabilization_ms": 10000,
            "stable_start_runs": 2,
            "minimum_free_vram_gib": 0.5 if backend == "cuda" else None,
            "vram_release_tolerance_gib": 0.125 if backend == "cuda" else None,
            "candidates": [policy_candidate],
        },
        "hardware": _hardware(backend),
        "hardware_class": "ram-32-vram-8",
        "modes": {"coding": {"candidates": [candidate], "selected_candidate_id": "safe"}},
        "selection_rule": "max-median-tok-s-then-free-vram-then-prudent-envelope/v1",
        "privacy_reviewed": True,
        "evidence_manifest": "SHA256SUMS",
    }


def _profile(report_bytes: bytes, backend: str, engine: str) -> dict[str, object]:
    """Build a profile linked to the exact synthetic report bytes."""
    envelope: dict[str, object] = {
        "ctx": 8192,
        "tok_s": {"min": 1, "median": 3, "max": 5},
    }
    if backend == "cuda":
        envelope["n_cpu_moe"] = 48
    return {
        "schema": "profile/v1",
        "id": "synthetic-profile",
        "model": "owner/model:file",
        "engine": engine,
        "measured_on": "synthetic test host",
        "calibration_protocol": "calibration/v1",
        "calibration_report": "synthetic-report",
        "calibration_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "benchmark_protocol": "benchmark/v1",
        "match": {
            "backend": backend,
            "vram_gib": [7, 9] if backend == "cuda" else [0, None],
            "ram_gib": [31, 33],
            "os": ["linux"],
        },
        "modes": {"coding": envelope},
    }


def build_valid_content(
    tmp_path: Path, backend: str = "cuda", engine: str = "b10011"
) -> ContentFiles:
    """Create linked report/profile fixture content under an isolated resource root."""
    root = copy_resource_root(tmp_path)
    write_json(root / "content/calibration-policy.json", valid_policy(backend, engine))
    report_path = root / "content/calibrations/synthetic-report.json"
    profile_path = root / "content/profiles/synthetic-profile.json"
    write_json(report_path, valid_report(backend, engine))
    write_json(profile_path, _profile(report_path.read_bytes(), backend, engine))
    return ContentFiles(root, report_path, profile_path)


def refresh_profile_digest(files: ContentFiles) -> None:
    """Update a synthetic profile after an intentional report mutation."""
    profile = read_json(files.profile)
    profile["calibration_report_sha256"] = hashlib.sha256(files.report.read_bytes()).hexdigest()
    write_json(files.profile, profile)
