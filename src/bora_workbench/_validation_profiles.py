"""Validate the packaged runtime catalog: mode identities and profile/v1 shared seeds.

The module owns the documents `profiles.load_catalog` turns into runtime models. A mode must own
its file name, and a profile must reproduce the accepted calibration report it names: the exact
report bytes, the selected candidate envelope, the measured hardware, and the policy class the
report was approved under; those references and digests are checked semantically as specification
section 5.3 requires. D-034 forbids presenting another machine's measurement as a local
calibration, so a profile may never widen the window its evidence supports. A profile measured on
a superseded engine release stays structurally valid and is only reported as a warning.
"""

from __future__ import annotations

import hashlib
from itertools import combinations
from typing import cast

from bora_workbench._validation_calibration import index_policies
from bora_workbench.validation import Document, JsonObject, ValidationIssue


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create a catalog error tied to its source document."""
    return ValidationIssue("error", document.file, path, message)


def collect_mode_ids(documents: tuple[Document, ...]) -> set[str]:
    """Return every packaged mode identifier that other content may reference."""
    return {
        cast(str, document.data["id"])
        for document in documents
        if document.data.get("schema") == "mode/v2"
    }


def validate_modes(documents: tuple[Document, ...]) -> list[ValidationIssue]:
    """Require every mode to own its file name and to declare a unique identifier."""
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for document in documents:
        if document.data.get("schema") != "mode/v2":
            continue
        mode_id = cast(str, document.data["id"])
        if mode_id != document.stem:
            issues.append(_error(document, "$.id", "must equal the file name"))
        if mode_id in seen:
            issues.append(_error(document, "$.id", f"duplicate mode id {mode_id!r}"))
        seen.add(mode_id)
    return issues


def _range_valid(values: object) -> bool:
    """Return whether an inclusive range has ordered finite endpoints."""
    minimum, maximum = cast(list[float | None], values)
    return maximum is None or cast(float, minimum) <= maximum


def _range_contains(values: object, number: float) -> bool:
    """Return whether one exact hardware value lies in an inclusive range."""
    minimum, maximum = cast(list[float | None], values)
    return cast(float, minimum) <= number and (maximum is None or number <= maximum)


def _ranges_overlap(left: object, right: object) -> bool:
    """Return whether two inclusive ranges share a value."""
    left_min, left_max = cast(list[float | None], left)
    right_min, right_max = cast(list[float | None], right)
    left_end = float("inf") if left_max is None else left_max
    right_end = float("inf") if right_max is None else right_max
    return cast(float, left_min) <= right_end and cast(float, right_min) <= left_end


def _local_issues(document: Document, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate profile-only range, benchmark, backend, and reference rules."""
    data = document.data
    match = cast(JsonObject, data["match"])
    backend = cast(str, match["backend"])
    modes = cast(JsonObject, data["modes"])
    issues: list[ValidationIssue] = []
    if data["id"] != document.stem:
        issues.append(_error(document, "$.id", "must equal the file name"))
    for field in ("ram_gib", "vram_gib"):
        if not _range_valid(match[field]):
            issues.append(_error(document, f"$.match.{field}", "minimum must not exceed maximum"))
    for mode_id, value in modes.items():
        path = f"$.modes.{mode_id}"
        envelope = cast(JsonObject, value)
        if mode_id not in mode_ids:
            issues.append(_error(document, path, "references an unknown mode"))
        if backend == "cuda" and "n_cpu_moe" not in envelope:
            issues.append(_error(document, f"{path}.n_cpu_moe", "required for CUDA"))
        if backend == "cpu" and "n_cpu_moe" in envelope:
            issues.append(_error(document, f"{path}.n_cpu_moe", "forbidden for CPU"))
        if "tok_s" in envelope:
            rates = cast(JsonObject, envelope["tok_s"])
            values = (float(rates["min"]), float(rates["median"]), float(rates["max"]))
            if not values[0] <= values[1] <= values[2]:
                issues.append(
                    _error(document, f"{path}.tok_s", "must satisfy min <= median <= max")
                )
    return issues


def _selected_candidate(report: Document, mode_id: str) -> JsonObject | None:
    """Return the selected candidate object for one accepted report mode."""
    report_modes = cast(JsonObject, report.data["modes"])
    if mode_id not in report_modes:
        return None
    mode = cast(JsonObject, report_modes[mode_id])
    selected_id = mode["selected_candidate_id"]
    candidates = cast(list[JsonObject], mode["candidates"])
    return next((candidate for candidate in candidates if candidate["id"] == selected_id), None)


def _envelope_issues(document: Document, report: Document) -> list[ValidationIssue]:
    """Require every profile envelope to equal its report-selected candidate."""
    issues: list[ValidationIssue] = []
    modes = cast(JsonObject, document.data["modes"])
    for mode_id, value in modes.items():
        path = f"$.modes.{mode_id}"
        envelope = cast(JsonObject, value)
        selected = _selected_candidate(report, mode_id)
        if selected is None:
            issues.append(_error(document, path, "missing selected candidate in report"))
            continue
        for field in ("ctx", "n_cpu_moe"):
            if envelope.get(field) != selected.get(field):
                issues.append(
                    _error(document, f"{path}.{field}", "differs from selected candidate")
                )
        if "tok_s" in envelope and envelope["tok_s"] != selected["tok_s"]:
            issues.append(_error(document, f"{path}.tok_s", "differs from selected candidate"))
    return issues


def _hardware_issues(document: Document, report: Document) -> list[ValidationIssue]:
    """Require report backend, OS, RAM, and VRAM to fit the profile class."""
    match = cast(JsonObject, document.data["match"])
    hardware = cast(JsonObject, report.data["hardware"])
    issues: list[ValidationIssue] = []
    if match["backend"] != hardware["backend"]:
        issues.append(_error(document, "$.match.backend", "differs from calibration report"))
    systems = cast(list[str], match.get("os", []))
    if systems and hardware["os_name"] not in systems:
        issues.append(_error(document, "$.match.os", "does not include calibration report OS"))
    ram = float(cast(float, hardware["ram_total_gib"]))
    if not _range_contains(match["ram_gib"], ram):
        issues.append(_error(document, "$.match.ram_gib", "does not contain measured RAM"))
    if match["backend"] == "cuda":
        vram = float(cast(float, hardware["vram_total_gib"]))
        if not _range_contains(match["vram_gib"], vram):
            issues.append(_error(document, "$.match.vram_gib", "does not contain measured VRAM"))
    return issues


def _report_issues(
    document: Document, report: Document | None, engine: JsonObject
) -> list[ValidationIssue]:
    """Check report existence, digest, acceptance, identity, and measured envelope."""
    if report is None:
        return [_error(document, "$.calibration_report", "referenced report is missing")]
    issues: list[ValidationIssue] = []
    digest = hashlib.sha256(report.raw_bytes).hexdigest()
    if document.data["calibration_report_sha256"] != digest:
        issues.append(
            _error(document, "$.calibration_report_sha256", "does not match report bytes")
        )
    if report.data["decision"] != "accepted":
        issues.append(_error(document, "$.calibration_report", "report is not accepted"))
    for field in ("model", "engine"):
        if document.data[field] != report.data[field]:
            issues.append(_error(document, f"$.{field}", "differs from calibration report"))
    if document.data["engine"] == engine.get("release") and report.data[
        "engine_source_commit"
    ] != engine.get("source_commit"):
        issues.append(_error(document, "$.engine", "report source commit differs from lock"))
    issues.extend(_hardware_issues(document, report))
    issues.extend(_envelope_issues(document, report))
    return issues


def _class_issues(
    document: Document, report: Document | None, policies: dict[str, JsonObject]
) -> list[ValidationIssue]:
    """Compare one profile match object with its named class and measured operating system."""
    if report is None:
        return []
    policy_id = cast(JsonObject, report.data["policy"])["id"]
    policy = policies.get(cast(str, policy_id)) if policy_id is not None else None
    if policy is None:
        return []
    classes = cast(list[JsonObject], policy["hardware_classes"])
    class_id = report.data["hardware_class"]
    hardware_class = next((item for item in classes if item["id"] == class_id), None)
    if hardware_class is None:
        return []
    match = cast(JsonObject, document.data["match"])
    issues: list[ValidationIssue] = []
    for field in ("ram_gib", "vram_gib"):
        if match[field] != hardware_class[field]:
            message = "differs from the report's approved policy class"
            issues.append(_error(document, f"$.match.{field}", message))
    hardware = cast(JsonObject, report.data["hardware"])
    if match.get("os") != [hardware["os_name"]]:
        message = "must contain only the operating system measured by the report"
        issues.append(_error(document, "$.match.os", message))
    return issues


def _profile_overlap(left: Document, right: Document) -> bool:
    """Return whether two profiles can apply to the same OS, backend, memory, and mode."""
    left_match = cast(JsonObject, left.data["match"])
    right_match = cast(JsonObject, right.data["match"])
    if any(left.data[field] != right.data[field] for field in ("model", "engine")):
        return False
    if left_match["backend"] != right_match["backend"]:
        return False
    left_os = set(cast(list[str], left_match.get("os", ["linux", "windows"])))
    right_os = set(cast(list[str], right_match.get("os", ["linux", "windows"])))
    if not left_os & right_os or not set(cast(JsonObject, left.data["modes"])) & set(
        cast(JsonObject, right.data["modes"])
    ):
        return False
    if not _ranges_overlap(left_match["ram_gib"], right_match["ram_gib"]):
        return False
    return left_match["backend"] == "cpu" or _ranges_overlap(
        left_match["vram_gib"], right_match["vram_gib"]
    )


def validate_profiles(
    documents: tuple[Document, ...], mode_ids: set[str], engine: JsonObject
) -> list[ValidationIssue]:
    """Return all local, report-linked, class-provenance, and overlap profile issues."""
    reports = {
        cast(str, item.data["id"]): item
        for item in documents
        if item.data.get("schema") == "calibration-report/v1"
    }
    policies = index_policies(documents)
    profiles = [item for item in documents if item.data.get("schema") == "profile/v1"]
    issues: list[ValidationIssue] = []
    for profile in profiles:
        issues.extend(_local_issues(profile, mode_ids))
        report = reports.get(cast(str, profile.data["calibration_report"]))
        issues.extend(_report_issues(profile, report, engine))
        if profile.data["engine"] != engine.get("release"):
            message = "engine differs from engine.lock; profile is not calibrated at runtime"
            issues.append(ValidationIssue("warning", profile.file, "$.engine", message))
        issues.extend(_class_issues(profile, report, policies))
    for left, right in combinations(profiles, 2):
        if _profile_overlap(left, right):
            issues.append(
                _error(right, "$.match", f"overlaps profile {cast(str, left.data['id'])!r}")
            )
    return issues
