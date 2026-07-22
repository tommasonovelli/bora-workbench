"""Evaluate supported active calibration records and pending candidates for safe local reuse."""

from __future__ import annotations

from typing import cast

from qwen_launcher._calibration_record import (
    JsonObject,
    RecordError,
    RecordSupersededError,
    candidate_record_path,
    command_contract_sha256,
    load_record,
    record_path,
)
from qwen_launcher._calibration_reuse_types import (
    CandidateStatus,
    RecordEvaluation,
    ReuseQuery,
)
from qwen_launcher._hardware_monitoring import query_gpu_snapshot
from qwen_launcher.hardware import HardwareError

_RAM_IDENTITY_TOLERANCE_GIB = 1 / 1024


def _ram_identity_mismatch(recorded: object, current: float) -> str | None:
    """Ignore sub-MiB OS reporting jitter without hiding a material RAM capacity change."""
    difference_gib = abs(float(cast(float, recorded)) - current)
    if difference_gib <= _RAM_IDENTITY_TOLERANCE_GIB:
        return None
    return f"total RAM GiB changed (recorded {recorded!r}, current {current!r})"


def _identity_mismatches(record: JsonObject, query: ReuseQuery) -> list[str]:
    """List every identity divergence between the record and current state."""
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
        ("GPU count", hardware["gpu_count"], current.gpu_count),
        ("GPU", hardware["gpu_name"], current.gpu_name),
        ("total VRAM GiB", hardware["vram_total_gib"], current.vram_total_gib),
    )
    mismatches = [
        f"{label} changed (recorded {recorded!r}, current {value!r})"
        for label, recorded, value in expected
        if recorded != value
    ]
    ram_mismatch = _ram_identity_mismatch(hardware["ram_total_gib"], current.ram_total_gib)
    if ram_mismatch is not None:
        mismatches.append(ram_mismatch)
    return mismatches


def _cuda_state(record: JsonObject, query: ReuseQuery) -> tuple[list[str], float | None]:
    """Compare recorded driver and read current free VRAM through one live snapshot."""
    if query.hardware.backend != "cuda":
        return [], None
    gpu_index = query.hardware.gpu_index
    assert gpu_index is not None
    try:
        snapshot = query_gpu_snapshot(gpu_index)
    except HardwareError as error:
        return [f"GPU state cannot be read for record reuse: {error}"], None
    recorded_driver = cast(JsonObject, record["hardware"])["gpu_driver"]
    if snapshot.driver_version == recorded_driver:
        return [], snapshot.vram_free_gib
    message = (
        f"GPU driver changed (recorded {recorded_driver!r}, current {snapshot.driver_version!r})"
    )
    return [message], None


def _headroom_issues(record: JsonObject, vram_free_gib: float | None, ram_gib: float) -> list[str]:
    """Require measured needs plus the exact reserves stored by the record's protocol."""
    observed = cast(JsonObject, record["observed"])
    search = cast(JsonObject, record["search"])
    ram_reserve_gib = float(cast(float, search["ram_reserve_gib"]))
    vram_reserve_gib = float(cast(float, search["vram_reserve_gib"]))
    issues: list[str] = []
    ram_required = float(cast(float, observed["ram_needed_gib"])) + ram_reserve_gib
    if ram_gib < ram_required:
        issues.append(
            f"available RAM {ram_gib:.2f} GiB is below measured need plus the "
            f"{ram_reserve_gib} GiB reserve ({ram_required:.2f} GiB)"
        )
    vram_needed = cast(float | None, observed["vram_needed_gib"])
    if vram_needed is not None and vram_free_gib is not None:
        required = float(vram_needed) + vram_reserve_gib
        if vram_free_gib < required:
            issues.append(
                f"free VRAM {vram_free_gib:.2f} GiB is below measured need plus the "
                f"{vram_reserve_gib} GiB reserve ({required:.2f} GiB)"
            )
    return issues


def _candidate_state(mode_id: str) -> tuple[CandidateStatus, tuple[str, ...]]:
    """Validate a pending candidate separately because it must never steer a launch."""
    path = candidate_record_path(mode_id)
    if not path.is_file():
        return "missing", ()
    try:
        load_record(path)
    except RecordSupersededError as error:
        return "superseded", (str(error),)
    except RecordError as error:
        return "invalid", (str(error),)
    return "valid", (f"pending candidate {path}; use `qwen-launcher calibrate --activate`",)


def _with_candidate(evaluation: RecordEvaluation, mode_id: str) -> RecordEvaluation:
    """Attach pending-candidate diagnostics to an already determined active state."""
    status, diagnostics = _candidate_state(mode_id)
    return RecordEvaluation(
        evaluation.status,
        evaluation.ctx,
        evaluation.n_cpu_moe,
        evaluation.diagnostics,
        status,
        diagnostics,
    )


def _missing_evaluation(query: ReuseQuery) -> RecordEvaluation:
    """Distinguish no active record from a valid pending candidate."""
    candidate_status, candidate_diagnostics = _candidate_state(query.mode_id)
    if candidate_status == "valid":
        message = "pending calibration candidate is not active; use `calibrate --activate`"
        return RecordEvaluation(
            "candidate", None, None, (message,), candidate_status, candidate_diagnostics
        )
    if candidate_status == "superseded":
        return RecordEvaluation(
            "superseded", None, None, candidate_diagnostics, candidate_status, candidate_diagnostics
        )
    message = "no local calibration record; run `qwen-launcher calibrate` to optimize locally"
    return RecordEvaluation(
        "missing", None, None, (message,), candidate_status, candidate_diagnostics
    )


def evaluate_record(query: ReuseQuery) -> RecordEvaluation:
    """Evaluate one mode's active record and expose pending candidate state separately."""
    path = record_path(query.mode_id)
    if not path.is_file():
        return _missing_evaluation(query)
    try:
        record = load_record(path)
    except RecordSupersededError as error:
        return _with_candidate(
            RecordEvaluation("superseded", None, None, (str(error),)), query.mode_id
        )
    except RecordError as error:
        return _with_candidate(
            RecordEvaluation("invalid", None, None, (str(error),)), query.mode_id
        )
    mismatches = _identity_mismatches(record, query)
    driver_issues, vram_free_gib = _cuda_state(record, query)
    mismatches.extend(driver_issues)
    envelope = cast(JsonObject, record["envelope"])
    ctx = cast(int, envelope["ctx"])
    n_cpu_moe = cast(int | None, envelope["n_cpu_moe"])
    if mismatches:
        diagnostics = tuple(f"local calibration record ignored: {issue}" for issue in mismatches)
        return _with_candidate(
            RecordEvaluation("incompatible", ctx, n_cpu_moe, diagnostics), query.mode_id
        )
    headroom = _headroom_issues(record, vram_free_gib, query.hardware.ram_available_gib)
    if headroom:
        diagnostics = tuple(f"local calibration record not usable now: {item}" for item in headroom)
        return _with_candidate(
            RecordEvaluation("insufficient-headroom", ctx, n_cpu_moe, diagnostics), query.mode_id
        )
    return _with_candidate(RecordEvaluation("valid", ctx, n_cpu_moe, ()), query.mode_id)
