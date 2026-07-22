"""Generate and atomically promote privacy-safe local calibration contribution bundles."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import shutil
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from qwen_launcher._calibration_documents import (
    DocumentContext,
    LogEvidence,
    build_benchmarks,
    build_profile_proposal,
    build_report,
)
from qwen_launcher._calibration_privacy import redact_document, redact_text
from qwen_launcher._calibration_types import TrialResult
from qwen_launcher.calibration import (
    CalibrationError,
    CalibrationOutcome,
    CalibrationSettings,
    CalibrationTarget,
)


@dataclass(slots=True)
class BundleWorkspace:
    """Own one same-directory staging tree until validated atomic promotion or cleanup."""

    root: Path
    report_id: str
    created_at: str
    staging_path: Path
    destination_path: Path

    @classmethod
    def create(cls, root: Path) -> BundleWorkspace:
        """Create a unique managed staging tree and reserve its immutable destination name."""
        now = datetime.now(UTC)
        report_id = "calibration-" + now.strftime("%Y%m%dt%H%M%S%f")
        root.mkdir(parents=True, exist_ok=True)
        destination = root / report_id
        staging = root / f".{report_id}.tmp-{uuid4().hex}"
        if destination.exists():
            raise CalibrationError(f"calibration bundle already exists: {destination}")
        staging.mkdir()
        return cls(root, report_id, now.isoformat().replace("+00:00", "Z"), staging, destination)

    @property
    def runtime_path(self) -> Path:
        """Return the private transient process-state tree removed before promotion."""
        path = self.staging_path / ".runtime"
        path.mkdir(exist_ok=True)
        return path

    def abort(self) -> None:
        """Remove only this unpromoted staging tree after verifying managed ancestry."""
        try:
            self.staging_path.relative_to(self.root)
        except ValueError as error:
            raise CalibrationError(
                "refusing to clean calibration staging outside its root"
            ) from error
        shutil.rmtree(self.staging_path, ignore_errors=True)

    def finalize(
        self,
        target: CalibrationTarget,
        settings: CalibrationSettings,
        trials: TrialResult,
    ) -> CalibrationOutcome:
        """Write, validate, and atomically promote the complete draft evidence bundle."""
        private_values = _private_values(target, self.staging_path)
        logs = _copy_logs(self.staging_path, trials, private_values)
        context = DocumentContext(self.report_id, self.created_at, target, settings, trials, logs)
        report_name = f"{self.report_id}.json"
        documents = (
            (report_name, build_report(context)),
            ("benchmark-results.json", build_benchmarks(context)),
            ("profile-proposal.json", build_profile_proposal(context)),
        )
        for name, document in documents:
            safe = cast(dict[str, object], redact_document(document, private_values))
            _write_json(self.staging_path / name, safe)
        _write_guide(self.staging_path / "CONTRIBUTING.md", report_name)
        shutil.rmtree(self.staging_path / ".runtime", ignore_errors=True)
        _write_manifest(self.staging_path)
        from qwen_launcher._calibration_validation import validate_bundle

        validation = validate_bundle(self.staging_path)
        if validation.errors:
            first = validation.errors[0]
            raise CalibrationError(
                f"generated bundle is invalid: {first.file}:{first.field_path}: {first.message}"
            )
        self.staging_path.replace(self.destination_path)
        selections = tuple((mode.mode.id, mode.proposed_candidate_id) for mode in trials.modes)
        return CalibrationOutcome(self.destination_path, self.report_id, selections)


def _write_json(path: Path, value: dict[str, object]) -> None:
    """Write deterministic JSON through a flushed same-directory temporary file."""
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2, ensure_ascii=False)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def _private_values(target: CalibrationTarget, staging: Path) -> tuple[str, ...]:
    """Enumerate known host identity and absolute path values that cannot enter shared logs."""
    values = {
        getpass.getuser(),
        socket.gethostname(),
        str(Path.home()),
        str(target.executable),
        str(target.model_path),
        str(staging),
    }
    if target.mmproj_path is not None:
        values.add(str(target.mmproj_path))
    expanded = values | {value.replace("\\", "/") for value in values}
    return tuple(sorted((value for value in expanded if value), key=len, reverse=True))


def _sanitized_log(source: Path, private_values: tuple[str, ...]) -> bytes:
    """Redact known host identity and private paths from one UTF-8 process log."""
    try:
        text = source.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        text = f"Log unavailable during bundle generation: {error.__class__.__name__}\n"
    return redact_text(text, private_values).encode("utf-8")


def _copy_logs(staging: Path, trials: TrialResult, private_values: tuple[str, ...]) -> LogEvidence:
    """Copy redacted logs and return report-relative SHA-256 evidence by mode/candidate."""
    evidence: LogEvidence = {}
    for mode in trials.modes:
        for trial in mode.candidates:
            directory = staging / "logs" / mode.mode.id / trial.candidate.id
            directory.mkdir(parents=True, exist_ok=True)
            sources = trial.log_paths
            entries: list[tuple[str, str]] = []
            source_values: tuple[Path | None, ...] = sources or (None,)
            for index, source in enumerate(source_values, start=1):
                destination = directory / f"run-{index}.log"
                if source is None:
                    reason = trial.discard_reason or "Candidate completed without a process log."
                    data = redact_text(reason + "\n", private_values).encode("utf-8")
                else:
                    data = _sanitized_log(source, private_values)
                destination.write_bytes(data)
                relative = destination.relative_to(staging).as_posix()
                entries.append((relative, hashlib.sha256(data).hexdigest()))
            evidence[(mode.mode.id, trial.candidate.id)] = tuple(entries)
    return evidence


def _write_guide(path: Path, report_name: str) -> None:
    """Write the manual-only review and contribution sequence for this draft bundle."""
    text = f"""# Calibration draft bundle

This bundle is local and unaccepted. It does not modify the repository or publish data.

1. Inspect `{report_name}`, `profile-proposal.json`, all redacted logs, and `SHA256SUMS`.
2. Confirm privacy manually; the report intentionally keeps `privacy_reviewed=false`.
3. Run `qwen-launcher validate --path <this-directory>`.
4. Keep this laboratory bundle local unless it is needed for diagnostics.
5. Do not submit it as v4 evidence or copy its proposal into packaged profiles; shared evidence
   requires a separate calibration/v4 run and the project's calibration contribution review.
"""
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_manifest(root: Path) -> None:
    """Write deterministic SHA-256 entries for every shareable file except the manifest itself."""
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}"
        for path in files
    ]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
