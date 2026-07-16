"""Build privacy-safe draft report, benchmark, and profile-proposal documents."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from qwen_launcher._calibration_types import CandidateTrial, TrialResult
from qwen_launcher.calibration import CalibrationSettings, CalibrationTarget

LogEvidence = dict[tuple[str, str], tuple[tuple[str, str], ...]]
_SELECTION_RULE = "max-median-tok-s-then-free-vram-then-prudent-envelope/v1"


@dataclass(frozen=True, slots=True)
class DocumentContext:
    """Group immutable inputs shared by all generated bundle documents."""

    report_id: str
    created_at: str
    target: CalibrationTarget
    settings: CalibrationSettings
    trials: TrialResult
    logs: LogEvidence


def _launcher_version() -> str:
    """Read installed package metadata with the source-checkout development fallback."""
    try:
        return version("qwen-launcher")
    except PackageNotFoundError:
        return "0.1.0.dev0"


def _hardware(context: DocumentContext) -> dict[str, object]:
    """Serialize only calibration-report/v1 hardware facts without host identity or paths."""
    hardware = context.target.hardware
    return {
        "os_name": hardware.os_name,
        "os_version": hardware.os_version,
        "cpu_name": hardware.cpu_name,
        "cpu_cores": hardware.cpu_cores,
        "ram_total_gib": hardware.ram_total_gib,
        "ram_available_gib": hardware.ram_available_gib,
        "backend": hardware.backend,
        "gpu_index": hardware.gpu_index,
        "gpu_name": hardware.gpu_name,
        "gpu_driver": context.trials.gpu_driver,
        "vram_total_gib": hardware.vram_total_gib,
        "vram_free_gib": hardware.vram_free_gib,
    }


def _policy_candidates(context: DocumentContext) -> list[dict[str, object]]:
    """Flatten exact mode/candidate order into the report policy snapshot."""
    values: list[dict[str, object]] = []
    for mode in context.trials.modes:
        for candidate in context.settings.candidates:
            value: dict[str, object] = {
                "mode": mode.mode.id,
                "id": candidate.id,
                "ctx": candidate.ctx,
            }
            if candidate.n_cpu_moe is not None:
                value["n_cpu_moe"] = candidate.n_cpu_moe
            values.append(value)
    return values


def _summary(trial: CandidateTrial) -> dict[str, float] | None:
    """Serialize a valid benchmark summary or null discarded evidence."""
    if trial.benchmark is None:
        return None
    rates = trial.benchmark.tok_s
    return {"min": rates.minimum, "median": rates.median, "max": rates.maximum}


def _candidate(context: DocumentContext, mode_id: str, trial: CandidateTrial) -> dict[str, object]:
    """Serialize one candidate result under the strict calibration-report/v1 contract."""
    benchmark = trial.benchmark
    vram = trial.vram
    value: dict[str, object] = {
        "id": trial.candidate.id,
        "ctx": trial.candidate.ctx,
        "outcome": trial.outcome,
        "successful_start_runs": trial.successful_start_runs,
        "vram_baseline_gib": None if vram is None else vram.baseline_used_gib,
        "vram_peak_gib": None if vram is None else vram.peak_used_gib,
        "vram_min_free_gib": None if vram is None else vram.minimum_free_gib,
        "warmup_tok_s": None if benchmark is None else benchmark.warmup_tok_s,
        "measured_tok_s": None if benchmark is None else list(benchmark.measured_tok_s),
        "tok_s": _summary(trial),
        "log_digests": [
            {"path": path, "sha256": digest}
            for path, digest in context.logs[(mode_id, trial.candidate.id)]
        ],
    }
    if trial.candidate.n_cpu_moe is not None:
        value["n_cpu_moe"] = trial.candidate.n_cpu_moe
    if trial.discard_reason is not None:
        value["discard_reason"] = trial.discard_reason
    return value


def build_report(context: DocumentContext) -> dict[str, object]:
    """Build an unaccepted report whose proposed selections remain explicitly null."""
    modes = {
        mode.mode.id: {
            "candidates": [
                _candidate(context, mode.mode.id, candidate) for candidate in mode.candidates
            ],
            "selected_candidate_id": None,
        }
        for mode in context.trials.modes
    }
    return {
        "schema": "calibration-report/v1",
        "id": context.report_id,
        "created_at": context.created_at,
        "decision": "draft",
        "launcher_version": _launcher_version(),
        "model": context.target.config.model,
        "engine": context.target.lock["release"],
        "engine_source_commit": context.target.lock["source_commit"],
        "calibration_protocol": "calibration/v1",
        "benchmark_protocol": "benchmark/v1",
        "policy": {
            "id": None,
            "gpu_poll_interval_ms": 250,
            "stable_start_runs": context.settings.stable_start_runs,
            "minimum_free_vram_gib": context.settings.minimum_free_vram_gib,
            "candidates": _policy_candidates(context),
        },
        "hardware": _hardware(context),
        "hardware_class": None,
        "modes": modes,
        "selection_rule": _SELECTION_RULE,
        "privacy_reviewed": False,
        "evidence_manifest": "SHA256SUMS",
    }


def build_benchmarks(context: DocumentContext) -> dict[str, object]:
    """Build path-free benchmark/v1 results while omitting raw server response identities."""
    modes: dict[str, object] = {}
    for mode in context.trials.modes:
        modes[mode.mode.id] = {
            trial.candidate.id: {
                "outcome": trial.outcome,
                "warmup_tok_s": None if trial.benchmark is None else trial.benchmark.warmup_tok_s,
                "measured_tok_s": (
                    None if trial.benchmark is None else list(trial.benchmark.measured_tok_s)
                ),
                "tok_s": _summary(trial),
            }
            for trial in mode.candidates
        }
    return {
        "protocol": "benchmark/v1",
        "prompt_sha256": "1c7182235411da2d4fe6fca130e3effb0b0d965569c52abd8fd45327103ddb2e",
        "request_sha256": "025dc91aeb61a790d5fd36c27f127e04761ae7f1c3d6b542d0cfd9d37bc5c19f",
        "warmup_runs": 1,
        "measured_runs": 5,
        "modes": modes,
    }


def build_profile_proposal(context: DocumentContext) -> dict[str, object]:
    """Build a clearly non-distributable proposal without inventing a hardware window."""
    modes: dict[str, object] = {}
    for mode in context.trials.modes:
        selected = next(
            (
                trial
                for trial in mode.candidates
                if trial.candidate.id == mode.proposed_candidate_id
            ),
            None,
        )
        modes[mode.mode.id] = {
            "proposed_candidate_id": mode.proposed_candidate_id,
            "ctx": None if selected is None else selected.candidate.ctx,
            "n_cpu_moe": None if selected is None else selected.candidate.n_cpu_moe,
            "tok_s": None if selected is None else _summary(selected),
        }
    return {
        "status": "draft-not-distributable",
        "model": context.target.config.model,
        "engine": context.target.lock["release"],
        "calibration_report": context.report_id,
        "hardware_class": None,
        "match": None,
        "modes": modes,
        "next_step": "Calibration Gate must approve policy, windows, and selections.",
    }
