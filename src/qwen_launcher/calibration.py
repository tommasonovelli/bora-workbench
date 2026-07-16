"""Prepare explicit calibration/v1 inputs and coordinate local candidate trials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from qwen_launcher.config import DEFAULT_MODEL, Config, load_config
from qwen_launcher.engine import JsonObject, load_engine_lock, locate, resolve_model
from qwen_launcher.hardware import HardwareInfo, detect_hardware, ensure_launch_supported
from qwen_launcher.paths import data_dir
from qwen_launcher.process import status_services
from qwen_launcher.profiles import (
    Catalog,
    Mode,
    PlanError,
    enforce_memory_gate,
    load_catalog,
)

_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")
Backend = Literal["cuda", "cpu"]


class CalibrationError(RuntimeError):
    """Report an expected preflight, candidate, evidence, or bundle failure."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """Describe one explicitly supplied calibration envelope candidate."""

    id: str
    ctx: int
    n_cpu_moe: int | None


@dataclass(frozen=True, slots=True)
class CalibrationSettings:
    """Hold policy-free Step 5A values supplied explicitly by the operator."""

    candidates: tuple[Candidate, ...]
    stable_start_runs: int
    minimum_free_vram_gib: float | None
    vram_release_tolerance_gib: float | None


@dataclass(frozen=True, slots=True)
class CalibrationTarget:
    """Hold verified local artifacts and hardware for selected packaged modes."""

    config: Config
    hardware: HardwareInfo
    catalog: Catalog
    modes: tuple[Mode, ...]
    lock: JsonObject
    executable: Path
    model_path: Path
    mmproj_path: Path | None


@dataclass(frozen=True, slots=True)
class CalibrationOutcome:
    """Identify the atomically promoted draft bundle and proposed per-mode selections."""

    bundle_path: Path
    report_id: str
    proposed_selections: tuple[tuple[str, str | None], ...]


def parse_candidate(value: str, backend: Backend) -> Candidate:
    """Parse explicit ``ID:CTX[:N_CPU_MOE]`` input without assigning hidden defaults."""
    fields = value.split(":")
    expected = 3 if backend == "cuda" else 2
    if len(fields) != expected:
        syntax = "ID:CTX:N_CPU_MOE" if backend == "cuda" else "ID:CTX"
        raise CalibrationError(f"candidate must use {syntax} syntax for {backend}")
    candidate_id = fields[0]
    if not _ID_PATTERN.fullmatch(candidate_id):
        raise CalibrationError("candidate id must contain lowercase letters, digits, and hyphens")
    try:
        ctx = int(fields[1])
        n_cpu_moe = int(fields[2]) if backend == "cuda" else None
    except ValueError as error:
        raise CalibrationError("candidate context and n_cpu_moe must be integers") from error
    candidate = Candidate(candidate_id, ctx, n_cpu_moe)
    _validate_candidate(candidate, backend)
    return candidate


def _validate_candidate(candidate: Candidate, backend: Backend) -> None:
    """Apply report-schema and backend constraints before any process starts."""
    if candidate.ctx < 1024:
        raise CalibrationError(f"candidate {candidate.id!r} context must be at least 1024")
    if backend == "cuda" and (candidate.n_cpu_moe is None or candidate.n_cpu_moe < 0):
        raise CalibrationError(f"candidate {candidate.id!r} requires non-negative n_cpu_moe")
    if backend == "cpu" and candidate.n_cpu_moe is not None:
        raise CalibrationError(f"candidate {candidate.id!r} forbids n_cpu_moe on CPU")


def validate_settings(settings: CalibrationSettings, backend: Backend) -> None:
    """Require complete explicit Step 5A settings and preserve candidate order."""
    if not settings.candidates:
        raise CalibrationError("at least one explicit candidate is required without a policy")
    ids = [candidate.id for candidate in settings.candidates]
    if len(ids) != len(set(ids)):
        raise CalibrationError("candidate ids must be unique")
    for candidate in settings.candidates:
        _validate_candidate(candidate, backend)
    if settings.stable_start_runs < 1:
        raise CalibrationError("stable start runs must be at least 1")
    reserve = settings.minimum_free_vram_gib
    tolerance = settings.vram_release_tolerance_gib
    if backend == "cuda" and (reserve is None or reserve < 0):
        raise CalibrationError("minimum free VRAM GiB is required and non-negative on CUDA")
    if backend == "cuda" and (tolerance is None or tolerance < 0):
        raise CalibrationError("VRAM release tolerance GiB is required and non-negative on CUDA")
    if backend == "cpu" and (reserve is not None or tolerance is not None):
        raise CalibrationError("VRAM settings are forbidden on CPU")


def _selected_modes(mode_value: str, catalog: Catalog) -> tuple[Mode, ...]:
    """Resolve one mode or all packaged modes in deterministic catalog order."""
    if mode_value == "all":
        return catalog.modes
    mode = catalog.mode(mode_value)
    if mode is None:
        valid = ", ".join([mode.id for mode in catalog.modes] + ["all"])
        raise CalibrationError(f"unknown calibration mode {mode_value!r}; valid values: {valid}")
    return (mode,)


def prepare_target(mode_value: str) -> CalibrationTarget:
    """Verify local model, engine, memory, hardware, modes, and service exclusivity."""
    config = load_config()
    hardware = detect_hardware()
    enforce_memory_gate(config, hardware, force=False)
    ensure_launch_supported(hardware)
    if config.model != DEFAULT_MODEL:
        raise CalibrationError("calibration/v1 Step 5A supports only the pinned default model")
    report = status_services()
    if report.services:
        raise CalibrationError("a managed service is running; stop it before calibration")
    catalog = load_catalog()
    modes = _selected_modes(mode_value, catalog)
    lock = load_engine_lock()
    model = resolve_model(config, lock, require_vision=any(mode.services.vision for mode in modes))
    executable = locate(config, hardware.backend, lock)
    return CalibrationTarget(
        config,
        hardware,
        catalog,
        modes,
        lock,
        executable,
        model.model_path,
        model.mmproj_path,
    )


def run_calibration(
    target: CalibrationTarget,
    settings: CalibrationSettings,
    destination_root: Path | None = None,
) -> CalibrationOutcome:
    """Run every explicit candidate and atomically promote a privacy-safe draft bundle."""
    from qwen_launcher._calibration_bundle import BundleWorkspace
    from qwen_launcher._calibration_runner import run_trials

    backend = cast(Backend, target.hardware.backend)
    validate_settings(settings, backend)
    root = data_dir() / "calibrations" if destination_root is None else destination_root
    workspace = BundleWorkspace.create(root)
    try:
        trial = run_trials(target, settings, workspace.runtime_path)
        return workspace.finalize(target, settings, trial)
    except (OSError, PlanError) as error:
        workspace.abort()
        raise CalibrationError(str(error)) from error
    except BaseException:
        workspace.abort()
        raise
