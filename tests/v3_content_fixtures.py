"""Synthetic public calibration/v3 policy and evidence builders."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from tests.content_fixtures import copy_resource_root, read_json, write_json

_REPORT_ID = "synthetic-v3-reference"
_POLICY_ID = "synthetic-v3-policy"


@dataclass(frozen=True, slots=True)
class V3ContentFiles:
    """Point to one linked synthetic v3 policy and report resource root."""

    root: Path
    policy: Path
    report: Path


def _command_digest(lock: dict[str, object]) -> str:
    """Digest a test lock command contract with production canonicalization."""
    value = json.dumps(lock["command_contract"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


def _identity(lock: dict[str, object]) -> dict[str, object]:
    """Build exact public identity fields from one copied engine lock."""
    artifact = lock["default_model_artifact"]
    assert isinstance(artifact, dict)
    return {
        "model": lock["default_model"],
        "model_sha256": artifact["sha256"],
        "engine_release": lock["release"],
        "engine_source_commit": lock["source_commit"],
        "command_contract_sha256": _command_digest(lock),
    }


def _search() -> dict[str, object]:
    """Build the exact method snapshot shared by synthetic policy and report."""
    return {
        "context_scale": [131072, 65536, 32768, 16384, 8192],
        "probe_cap": 12,
        "vram_reserve_gib": 0.5,
        "ram_reserve_gib": 2.0,
        "release_tolerance_gib": 0.125,
        "confirm_rounds": 2,
        "confirmation_order": ["a", "b", "b", "a"],
        "selection_rule": "paired-round-unanimity-then-memory-margin-then-prudence",
    }


def _mode() -> dict[str, object]:
    """Build one coherent local observation whose seed cannot become an envelope."""
    return {
        "observed_local_envelope": {"ctx": 131072, "n_cpu_moe": 38},
        "seed_n_cpu_moe": 38,
        "probe_sequence": [
            {"n_cpu_moe": 41, "is_feasible": True},
            {"n_cpu_moe": 20, "is_feasible": False},
            {"n_cpu_moe": 38, "is_feasible": True},
        ],
        "finalists": [
            {"n_cpu_moe": 38, "outcome": "valid", "round_medians_tok_s": [20, 21]},
            {"n_cpu_moe": 39, "outcome": "valid", "round_medians_tok_s": [19, 20]},
        ],
        "selection_rule": "dominance-unanimous-rounds",
        "minimum_ram_available_gib": 8.5,
        "minimum_vram_free_gib": 0.75,
        "maximum_release_above_baseline_gib": 0.01,
        "baseline_drift_gib": 0.01,
    }


def valid_v3_report(lock: dict[str, object]) -> dict[str, object]:
    """Build schema-valid, privacy-safe reference evidence for one mode."""
    search = _search()
    search["n_cpu_moe_domain"] = {
        "minimum": 0,
        "maximum": 41,
        "maximum_source": "gguf-block-count",
    }
    return {
        "schema": "calibration-report/v2",
        "id": _REPORT_ID,
        "created_at": "2026-07-19T12:00:00Z",
        "decision": "accepted-reference",
        "privacy_reviewed": True,
        "policy_id": _POLICY_ID,
        "calibration_protocol": "calibration/v3",
        "benchmark_protocol": "benchmark/v1",
        **_identity(lock),
        "hardware": {
            "os_name": "windows",
            "os_version": "Windows 11 build 10.0.26200",
            "backend": "cuda",
            "ram_total_gib": 31.92,
            "gpu_name": "NVIDIA GeForce RTX 2060 SUPER",
            "gpu_driver": "610.47",
            "vram_total_gib": 8.0,
        },
        "gate": {
            "local_result": "calibration-accepted",
            "overall_status": "gate-partial",
            "constants_validated_on_materially_different_hardware": False,
            "heterogeneous_hardware_follow_up": "open-non-blocking",
        },
        "search": search,
        "modes": {"coding": _mode()},
        "seed_usage": "probe-ordering-only-complete-local-search",
        "performance_portability": "observed-values-are-not-promises",
        "source_references": [{"path": "docs/reference.md", "sha256": "0" * 64}],
    }


def _backends() -> dict[str, object]:
    """Build metadata-derived CUDA and honest CPU policy branches."""
    return {
        "cuda": {
            "axis": {
                "name": "n_cpu_moe",
                "minimum": 0,
                "maximum_source": "gguf-block-count",
                "expected_maximum": 41,
            },
            "seed_semantics": "reorder-only-complete-local-search",
        },
        "cpu": {
            "strategy": "engine-baseline-confirmation",
            "tuning_axis": None,
            "seed_semantics": "none",
        },
    }


def _coverage() -> dict[str, object]:
    """Build one explicitly partial measured scope for D-047."""
    scope = {
        "evidence_id": _REPORT_ID,
        "os_name": "windows",
        "os_version": "Windows 11 build 10.0.26200",
        "backend": "cuda",
        "gpu_name": "NVIDIA GeForce RTX 2060 SUPER",
        "vram_total_gib": 8.0,
        "ram_total_gib": 31.92,
    }
    return {
        "status": "gate-partial",
        "constants_validated_on_materially_different_hardware": False,
        "heterogeneous_hardware_follow_up": "open-non-blocking",
        "measured_scope": [scope],
    }


def valid_v3_policy(lock: dict[str, object], report_bytes: bytes) -> dict[str, object]:
    """Build a policy linked to exact synthetic report bytes."""
    search = _search()
    search.update({"gpu_poll_interval_ms": 250, "gpu_release_stabilization_ms": 10000})
    reference = {
        "id": _REPORT_ID,
        "path": f"calibrations/{_REPORT_ID}.json",
        "sha256": hashlib.sha256(report_bytes).hexdigest(),
    }
    return {
        "schema": "calibration-policy/v2",
        "id": _POLICY_ID,
        "calibration_protocol": "calibration/v3",
        "benchmark_protocol": "benchmark/v1",
        **_identity(lock),
        "objective": "maximum-context-then-paired-throughput-then-memory-margin-then-prudence",
        "modes": ["coding"],
        "backends": _backends(),
        "search": search,
        "empirical_coverage": _coverage(),
        "evidence": [reference],
    }


def build_v3_content(tmp_path: Path) -> V3ContentFiles:
    """Create one validated linked v3 policy/report resource root."""
    root = copy_resource_root(tmp_path)
    lock = read_json(root / "engine.lock")
    report = root / f"content/calibrations/{_REPORT_ID}.json"
    policy = root / "content/calibration-policy.json"
    write_json(report, valid_v3_report(lock))
    write_json(policy, valid_v3_policy(lock, report.read_bytes()))
    return V3ContentFiles(root, policy, report)
