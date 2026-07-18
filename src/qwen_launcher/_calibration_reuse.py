"""Decide whether a local calibration record is calibrated for the current launch.

Specification section 5.5 makes a record usable only when it was produced locally by
calibration/v2 and every identity field — model and artifact digest, engine release, commit and
command contract, mode, backend, OS, and stable hardware identity — matches the current state,
and only while current free RAM/VRAM covers the measured need plus the declared reserve. Any
divergence falls back to the baseline with actionable diagnostics; there is no nearest-match.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from qwen_launcher._calibration_record import (
    JsonObject,
    RecordError,
    command_contract_sha256,
    load_record,
    record_path,
)
from qwen_launcher._calibration_v2_types import VRAM_RESERVE_GIB
from qwen_launcher._hardware_monitoring import query_gpu_snapshot
from qwen_launcher.config import Config
from qwen_launcher.hardware import HardwareError, HardwareInfo

RecordStatus = Literal["valid", "missing", "invalid", "incompatible", "insufficient-headroom"]


@dataclass(frozen=True, slots=True)
class ReuseQuery:
    """Group the current identities a record must match before its envelope is reused."""

    config: Config
    mode_id: str
    hardware: HardwareInfo
    lock: JsonObject


@dataclass(frozen=True, slots=True)
class RecordEvaluation:
    """Report one record's reuse decision with its envelope or actionable diagnostics."""

    status: RecordStatus
    ctx: int | None
    n_cpu_moe: int | None
    diagnostics: tuple[str, ...]


def _identity_mismatches(record: JsonObject, query: ReuseQuery) -> list[str]:
    """List every identity divergence between the record and the current state."""
    artifact = cast(JsonObject, query.lock["default_model_artifact"])
    hardware = cast(JsonObject, record["hardware"])
    current = query.hardware
    expected: tuple[tuple[str, object, object], ...] = (
        ("model", record["model"], query.config.model),
        ("model artifact digest", record["model_sha256"], artifact["sha256"]),
        ("engine release", record["engine_release"], query.lock["release"]),
        ("engine source commit", record["engine_source_commit"], query.lock["source_commit"]),
        (
            "engine command contract",
            record["command_contract_sha256"],
            command_contract_sha256(query.lock),
        ),
        ("operating system", record["os_name"], current.os_name),
        ("backend", record["backend"], current.backend),
        ("CPU", hardware["cpu_name"], current.cpu_name),
        ("CPU cores", hardware["cpu_cores"], current.cpu_cores),
        ("total RAM GiB", hardware["ram_total_gib"], current.ram_total_gib),
        ("GPU count", hardware["gpu_count"], current.gpu_count),
        ("GPU", hardware["gpu_name"], current.gpu_name),
        ("total VRAM GiB", hardware["vram_total_gib"], current.vram_total_gib),
    )
    return [
        f"{label} changed (recorded {recorded!r}, current {value!r})"
        for label, recorded, value in expected
        if recorded != value
    ]


def _cuda_state(record: JsonObject, query: ReuseQuery) -> tuple[list[str], float | None]:
    """Compare the recorded driver and read current free VRAM through one live snapshot."""
    if query.hardware.backend != "cuda":
        return [], None
    gpu_index = query.hardware.gpu_index
    assert gpu_index is not None
    try:
        snapshot = query_gpu_snapshot(gpu_index)
    except HardwareError as error:
        return [f"GPU state cannot be read for record reuse: {error}"], None
    recorded_driver = cast(JsonObject, record["hardware"])["gpu_driver"]
    if snapshot.driver_version != recorded_driver:
        message = (
            f"GPU driver changed (recorded {recorded_driver!r}, "
            f"current {snapshot.driver_version!r})"
        )
        return [message], None
    return [], snapshot.vram_free_gib


def _headroom_issues(record: JsonObject, vram_free_gib: float | None, ram_gib: float) -> list[str]:
    """Require current free memory to cover the measured need plus the declared reserve."""
    observed = cast(JsonObject, record["observed"])
    issues: list[str] = []
    ram_needed = float(cast(float, observed["ram_needed_gib"]))
    if ram_gib < ram_needed:
        issues.append(
            f"available RAM {ram_gib:.2f} GiB is below the measured need {ram_needed:.2f} GiB"
        )
    vram_needed = cast(float | None, observed["vram_needed_gib"])
    if vram_needed is not None and vram_free_gib is not None:
        required = float(vram_needed) + VRAM_RESERVE_GIB
        if vram_free_gib < required:
            issues.append(
                f"free VRAM {vram_free_gib:.2f} GiB is below the measured need plus "
                f"the {VRAM_RESERVE_GIB} GiB reserve ({required:.2f} GiB)"
            )
    return issues


def evaluate_record(query: ReuseQuery) -> RecordEvaluation:
    """Evaluate one mode's local record against the current machine and contracts."""
    path = record_path(query.mode_id)
    if not path.is_file():
        message = "no local calibration record; run `qwen-launcher calibrate` to optimize locally"
        return RecordEvaluation("missing", None, None, (message,))
    try:
        record = load_record(path)
    except RecordError as error:
        return RecordEvaluation("invalid", None, None, (str(error),))
    mismatches = _identity_mismatches(record, query)
    if record["mode"] != query.mode_id:
        mismatches.append(f"record names mode {record['mode']!r} instead of {query.mode_id!r}")
    driver_issues, vram_free_gib = _cuda_state(record, query)
    mismatches.extend(driver_issues)
    envelope = cast(JsonObject, record["envelope"])
    ctx = cast(int, envelope["ctx"])
    n_cpu_moe = cast(int | None, envelope["n_cpu_moe"])
    if mismatches:
        diagnostics = tuple(f"local calibration record ignored: {issue}" for issue in mismatches)
        return RecordEvaluation("incompatible", ctx, n_cpu_moe, diagnostics)
    headroom = _headroom_issues(record, vram_free_gib, query.hardware.ram_available_gib)
    if headroom:
        diagnostics = tuple(
            f"local calibration record not usable now: {issue}" for issue in headroom
        )
        return RecordEvaluation("insufficient-headroom", ctx, n_cpu_moe, diagnostics)
    return RecordEvaluation("valid", ctx, n_cpu_moe, ())
