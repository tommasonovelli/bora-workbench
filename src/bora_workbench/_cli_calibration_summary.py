"""Explain the measured envelopes, gate outcomes, and retained record paths."""

from __future__ import annotations

from rich.console import Console

from bora_workbench._calibration_run_types import RunResult
from bora_workbench._calibration_runner import ModeResult
from bora_workbench._calibration_types import PREFERENCES, EnvelopeResult, Preference
from bora_workbench._cli_theme import print_note, print_success, print_warning


def _offload(envelope: EnvelopeResult) -> str:
    """Name the measured offload position, which a CPU backend does not have."""
    value = envelope.sample.n_cpu_moe
    return "baseline" if value is None else str(value)


def _memory(envelope: EnvelopeResult) -> str:
    """Describe the minimum memory margin measured while this envelope was running."""
    sample = envelope.sample
    values = [f"RAM available min {sample.ram_min_available_gib:.2f} GiB"]
    if sample.vram_min_free_gib is not None:
        values.append(f"VRAM free min {sample.vram_min_free_gib:.2f} GiB")
    return ", ".join(values)


def _envelope_line(preference: Preference, envelope: EnvelopeResult, is_active: bool) -> str:
    """Summarize one measured envelope and mark the one this record will launch with."""
    sample = envelope.sample
    marker = " (active)" if is_active else ""
    return (
        f"  {preference}{marker}: ctx={sample.ctx}, n_cpu_moe={_offload(envelope)}; "
        f"{sample.e2e_ms:.0f} ms short e2e, {sample.decode_tps:.2f} tok/s decode, "
        f"{sample.prefill_tps:.2f} tok/s prefill; {_memory(envelope)}"
    )


def _mode_lines(result: ModeResult, active: Preference) -> list[str]:
    """Build the per-mode header and one line per measured preference envelope."""
    lines = [f"{result.mode.id}: {len(result.samples)} measured sample(s)"]
    for preference in PREFERENCES:
        envelope = result.envelopes[preference]
        lines.append(_envelope_line(preference, envelope, preference == active))
    return lines


def show_outcome(result: RunResult, active: Preference, console: Console) -> None:
    """Print the three measured envelopes per mode, then the record and evidence locations."""
    state = "completed for every selected mode" if not result.failures else "completed partially"
    print_success(console, f"Local calibration {state}.")
    for mode_result in result.mode_results:
        for line in _mode_lines(mode_result, active):
            console.print(line)
    for path in result.record_paths:
        print_note(console, "Record", str(path))
    for failure in result.failures:
        print_warning(console, f"No record written for {failure}")
    console.print(f"Private run evidence: {result.evidence_path}")
    console.print("No private record or process log was uploaded.")
