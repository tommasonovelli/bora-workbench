"""Validate calibration-policy/v1 catalogs, calibration-report/v1 evidence, and their links.

The module owns one area of competence: the packaged calibration protocol content that predates
the public calibration/v3 method. It checks what a JSON Schema cannot express — a policy search
that stays at one fixed context and one ordered envelope axis, report evidence that reproduces its
own summaries and memory reserves, the deterministic winner of specification section 5.6, and the
exact policy snapshot a report claims to have run under.
"""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import combinations
from math import inf, isclose
from pathlib import PurePosixPath, PureWindowsPath
from statistics import median
from typing import cast

from bora_workbench.validation import Document, JsonObject, ValidationIssue

_GPU_FIELDS = ("gpu_index", "gpu_name", "gpu_driver", "vram_total_gib", "vram_free_gib")
_MEMORY_FIELDS = (
    "vram_baseline_gib",
    "vram_peak_gib",
    "vram_min_free_gib",
    "vram_release_used_gib",
)


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create a calibration content error tied to its source document."""
    return ValidationIssue("error", document.file, path, message)


def _backend(document: Document) -> str:
    """Return the backend one report measured, which decides every GPU-only rule."""
    return cast(str, cast(JsonObject, document.data["hardware"])["backend"])


def _stable_start_runs(document: Document) -> int:
    """Return the successful fresh starts required by one report's policy snapshot."""
    return cast(int, cast(JsonObject, document.data["policy"])["stable_start_runs"])


def _contains(values: object, measurement: float) -> bool:
    """Return whether an exact measurement belongs to an inclusive policy range."""
    minimum, maximum = cast(list[float | None], values)
    return cast(float, minimum) <= measurement and (maximum is None or measurement <= maximum)


def _overlaps(left: object, right: object) -> bool:
    """Return whether two inclusive ranges share at least one value."""
    left_min, left_max = cast(list[float | None], left)
    right_min, right_max = cast(list[float | None], right)
    left_end = inf if left_max is None else left_max
    right_end = inf if right_max is None else right_max
    return cast(float, left_min) <= right_end and cast(float, right_min) <= left_end


def index_policies(documents: tuple[Document, ...]) -> dict[str, JsonObject]:
    """Index the nested policy objects of every schema-valid catalog by identifier."""
    policies: dict[str, JsonObject] = {}
    for document in documents:
        if document.data.get("schema") != "calibration-policy/v1":
            continue
        for policy in cast(list[JsonObject], document.data["policies"]):
            policies[cast(str, policy["id"])] = policy
    return policies


def _gpu_protocol(documents: tuple[Document, ...]) -> tuple[int, int] | None:
    """Return the catalog-wide GPU polling and release-stabilization protocol."""
    protocol: tuple[int, int] | None = None
    for document in documents:
        if document.data.get("schema") != "calibration-policy/v1":
            continue
        protocol = (
            cast(int, document.data["gpu_poll_interval_ms"]),
            cast(int, document.data["gpu_release_stabilization_ms"]),
        )
    return protocol


def _duplicate_issues(
    document: Document, path: str, values: list[JsonObject]
) -> list[ValidationIssue]:
    """Report repeated identifiers in one semantic scope."""
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for index, value in enumerate(values):
        identifier = cast(str, value["id"])
        if identifier in seen:
            issues.append(_error(document, f"{path}[{index}].id", f"duplicate id {identifier!r}"))
        seen.add(identifier)
    return issues


def _range_issue(document: Document, path: str, values: object) -> ValidationIssue | None:
    """Reject an inclusive range whose finite maximum is below its minimum."""
    minimum, maximum = cast(list[float | None], values)
    if maximum is not None and minimum is not None and minimum > maximum:
        return _error(document, path, "minimum must not exceed maximum")
    return None


def _policy_candidate_issues(
    document: Document, policy: JsonObject, base: str
) -> list[ValidationIssue]:
    """Validate unique candidate identifiers and backend-specific candidate fields."""
    backend = cast(str, policy["backend"])
    issues: list[ValidationIssue] = []
    for mode_id, mode_value in cast(JsonObject, policy["modes"]).items():
        path = f"{base}.modes.{mode_id}.candidates"
        candidates = cast(list[JsonObject], cast(JsonObject, mode_value)["candidates"])
        issues.extend(_duplicate_issues(document, path, candidates))
        for index, candidate in enumerate(candidates):
            has_value = "n_cpu_moe" in candidate
            if backend == "cuda" and not has_value:
                issues.append(_error(document, f"{path}[{index}].n_cpu_moe", "required for CUDA"))
            if backend == "cpu" and has_value:
                issues.append(_error(document, f"{path}[{index}].n_cpu_moe", "forbidden for CPU"))
    return issues


def _hardware_class_issues(
    document: Document, policy: JsonObject, base: str
) -> list[ValidationIssue]:
    """Validate hardware-class IDs, ranges, and non-overlap within one policy."""
    classes = cast(list[JsonObject], policy["hardware_classes"])
    path = f"{base}.hardware_classes"
    issues = _duplicate_issues(document, path, classes)
    for index, hardware_class in enumerate(classes):
        for field in ("ram_gib", "vram_gib"):
            found = _range_issue(document, f"{path}[{index}].{field}", hardware_class[field])
            if found:
                issues.append(found)
    for (_left_index, left), (right_index, right) in combinations(enumerate(classes), 2):
        if _overlaps(left["ram_gib"], right["ram_gib"]) and _overlaps(
            left["vram_gib"], right["vram_gib"]
        ):
            message = f"overlaps hardware class {cast(str, left['id'])!r}"
            issues.append(_error(document, f"{path}[{right_index}]", message))
    return issues


def _search_issues(document: Document, policy: JsonObject, base: str) -> list[ValidationIssue]:
    """Reject policy searches that compare contexts or repeat equivalent envelopes."""
    backend = cast(str, policy["backend"])
    issues: list[ValidationIssue] = []
    for mode_id, raw_mode in cast(JsonObject, policy["modes"]).items():
        candidates = cast(list[JsonObject], cast(JsonObject, raw_mode)["candidates"])
        path = f"{base}.modes.{mode_id}.candidates"
        if len({candidate["ctx"] for candidate in candidates}) != 1:
            issues.append(_error(document, path, "must use one fixed context"))
        if backend == "cpu" and len(candidates) > 1:
            issues.append(_error(document, path, "CPU has no varying envelope at fixed context"))
        if backend != "cuda" or any("n_cpu_moe" not in item for item in candidates):
            continue
        values = [candidate["n_cpu_moe"] for candidate in candidates]
        if len(values) != len(set(values)):
            issues.append(_error(document, path, "must use unique n_cpu_moe values"))
        if values != sorted(values, reverse=True):
            issues.append(_error(document, path, "must be ordered from prudent to aggressive"))
    return issues


def _policy_issues(document: Document, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate every policy of one catalog after its JSON Schema has passed."""
    policies = cast(list[JsonObject], document.data["policies"])
    issues = _duplicate_issues(document, "$.policies", policies)
    for index, policy in enumerate(policies):
        base = f"$.policies[{index}]"
        for mode_id in cast(JsonObject, policy["modes"]):
            if mode_id not in mode_ids:
                path = f"{base}.modes.{mode_id}"
                issues.append(_error(document, path, "references an unknown mode"))
        issues.extend(_policy_candidate_issues(document, policy, base))
        issues.extend(_hardware_class_issues(document, policy, base))
        issues.extend(_search_issues(document, policy, base))
    return issues


def _is_relative_path(value: str) -> bool:
    """Reject POSIX or Windows absolute, drive-relative, and parent-traversal paths."""
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return bool(value) and not (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    )


def _timestamp_issues(document: Document) -> list[ValidationIssue]:
    """Require the report timestamp to carry an explicit UTC offset."""
    value = cast(str, document.data["created_at"])
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return [_error(document, "$.created_at", "must be a valid date-time")]
    if timestamp.utcoffset() != UTC.utcoffset(timestamp):
        return [_error(document, "$.created_at", "must be expressed in UTC")]
    return []


def _hardware_issues(document: Document) -> list[ValidationIssue]:
    """Require GPU facts on CUDA and null GPU facts on CPU."""
    hardware = cast(JsonObject, document.data["hardware"])
    backend = cast(str, hardware["backend"])
    issues: list[ValidationIssue] = []
    for field in _GPU_FIELDS:
        value = hardware[field]
        if backend == "cpu" and value is not None:
            issues.append(_error(document, f"$.hardware.{field}", "must be null on CPU"))
        if backend == "cuda" and value is None:
            issues.append(_error(document, f"$.hardware.{field}", "must be present on CUDA"))
    policy = cast(JsonObject, document.data["policy"])
    for field in ("minimum_free_vram_gib", "vram_release_tolerance_gib"):
        value = policy[field]
        if backend == "cpu" and value is not None:
            issues.append(_error(document, f"$.policy.{field}", "must be null on CPU"))
        if backend == "cuda" and value is None:
            issues.append(_error(document, f"$.policy.{field}", "required on CUDA"))
    return issues


def _backend_field_issues(
    document: Document, path: str, value: JsonObject
) -> list[ValidationIssue]:
    """Validate backend-specific candidate and VRAM fields."""
    backend = _backend(document)
    issues: list[ValidationIssue] = []
    has_n_cpu_moe = "n_cpu_moe" in value
    if backend == "cuda" and not has_n_cpu_moe:
        issues.append(_error(document, f"{path}.n_cpu_moe", "required for CUDA"))
    if backend == "cpu" and has_n_cpu_moe:
        issues.append(_error(document, f"{path}.n_cpu_moe", "forbidden for CPU"))
    for field in _MEMORY_FIELDS:
        if field not in value:
            continue
        if backend == "cpu" and value[field] is not None:
            issues.append(_error(document, f"{path}.{field}", "must be null on CPU"))
        if backend == "cuda" and value[field] is None:
            issues.append(_error(document, f"{path}.{field}", "required on CUDA"))
    return issues


def _metric_issues(document: Document, path: str, candidate: JsonObject) -> list[ValidationIssue]:
    """Verify valid-run counts and exact min/median/max summaries."""
    if candidate["outcome"] != "valid":
        return []
    issues: list[ValidationIssue] = []
    starts = cast(int, candidate["successful_start_runs"])
    if starts < _stable_start_runs(document):
        issues.append(_error(document, f"{path}.successful_start_runs", "below policy"))
    measurements = cast(list[float], candidate["measured_tok_s"])
    summary = cast(JsonObject, candidate["tok_s"])
    expected = {"min": min(measurements), "median": median(measurements), "max": max(measurements)}
    for field, value in expected.items():
        if summary[field] != value:
            message = "does not match measurements"
            issues.append(_error(document, f"{path}.tok_s.{field}", message))
    return issues


def _mode_candidate_issues(
    document: Document, mode_id: str, mode: JsonObject
) -> list[ValidationIssue]:
    """Check candidate identity, ordering, evidence, and final selection for one mode."""
    base = f"$.modes.{mode_id}.candidates"
    candidates = cast(list[JsonObject], mode["candidates"])
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        candidate_id = cast(str, candidate["id"])
        path = f"{base}[{index}]"
        if candidate_id in seen:
            issues.append(_error(document, f"{path}.id", f"duplicate id {candidate_id!r}"))
        seen.add(candidate_id)
        issues.extend(_backend_field_issues(document, path, candidate))
        issues.extend(_metric_issues(document, path, candidate))
        logs = cast(list[JsonObject], candidate["log_digests"])
        for log_index, log in enumerate(logs):
            if not _is_relative_path(cast(str, log["path"])):
                log_path = f"{path}.log_digests[{log_index}].path"
                issues.append(_error(document, log_path, "must be relative"))
    selected_id = cast(str | None, mode["selected_candidate_id"])
    if selected_id is not None:
        selected = next((item for item in candidates if item["id"] == selected_id), None)
        if selected is None or selected["outcome"] != "valid":
            selection_path = f"$.modes.{mode_id}.selected_candidate_id"
            issues.append(_error(document, selection_path, "must reference a valid candidate"))
    return issues


def _snapshot_issues(document: Document, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate policy snapshot modes, backend fields, and candidate result order."""
    policy = cast(JsonObject, document.data["policy"])
    snapshot = cast(list[JsonObject], policy["candidates"])
    modes = cast(JsonObject, document.data["modes"])
    issues: list[ValidationIssue] = []
    for index, candidate in enumerate(snapshot):
        path = f"$.policy.candidates[{index}]"
        mode_id = cast(str, candidate["mode"])
        if mode_id not in mode_ids:
            issues.append(_error(document, f"{path}.mode", "references an unknown mode"))
        issues.extend(_backend_field_issues(document, path, candidate))
    for mode_id, mode_value in modes.items():
        expected = [item["id"] for item in snapshot if item["mode"] == mode_id]
        actual = [item["id"] for item in cast(JsonObject, mode_value)["candidates"]]
        if expected != actual:
            path = f"$.modes.{mode_id}.candidates"
            issues.append(_error(document, path, "order differs from policy snapshot"))
    return issues


def _report_issues(document: Document, mode_ids: set[str]) -> list[ValidationIssue]:
    """Validate one schema-valid report and all of its candidate evidence."""
    issues = _timestamp_issues(document) + _hardware_issues(document)
    if document.data["id"] != document.stem:
        issues.append(_error(document, "$.id", "must equal the file name"))
    manifest = cast(str, document.data["evidence_manifest"])
    if not _is_relative_path(manifest):
        issues.append(_error(document, "$.evidence_manifest", "must be relative"))
    modes = cast(JsonObject, document.data["modes"])
    for mode_id, mode_value in modes.items():
        if mode_id not in mode_ids:
            issues.append(_error(document, f"$.modes.{mode_id}", "references an unknown mode"))
        issues.extend(_mode_candidate_issues(document, mode_id, cast(JsonObject, mode_value)))
    issues.extend(_snapshot_issues(document, mode_ids))
    return issues


def _expected_candidates(policy: JsonObject, report: Document) -> list[JsonObject]:
    """Flatten policy candidates for only the modes exercised by one report."""
    report_modes = cast(JsonObject, report.data["modes"])
    expected: list[JsonObject] = []
    for mode_id, mode_value in cast(JsonObject, policy["modes"]).items():
        if mode_id not in report_modes:
            continue
        for candidate in cast(list[JsonObject], cast(JsonObject, mode_value)["candidates"]):
            expected.append({"mode": mode_id, **candidate})
    return expected


def _link_issues(
    report: Document, policies: dict[str, JsonObject], protocol: tuple[int, int] | None
) -> list[ValidationIssue]:
    """Require a named report policy snapshot to match its packaged policy exactly."""
    snapshot = cast(JsonObject, report.data["policy"])
    policy_id = cast(str | None, snapshot["id"])
    if policy_id is None:
        return []
    policy = policies.get(policy_id)
    if policy is None:
        return [_error(report, "$.policy.id", "references an unknown policy")]
    hardware = cast(JsonObject, report.data["hardware"])
    issues: list[ValidationIssue] = []
    for field in ("model", "engine"):
        if report.data[field] != policy[field]:
            issues.append(_error(report, f"$.{field}", "differs from referenced policy"))
    if hardware["backend"] != policy["backend"]:
        issues.append(_error(report, "$.hardware.backend", "differs from referenced policy"))
    if hardware["os_name"] not in cast(list[str], policy["os"]):
        issues.append(_error(report, "$.hardware.os_name", "not covered by referenced policy"))
    fields = ("stable_start_runs", "minimum_free_vram_gib", "vram_release_tolerance_gib")
    for field in fields:
        if snapshot[field] != policy.get(field):
            issues.append(_error(report, f"$.policy.{field}", "differs from referenced policy"))
    observed_protocol = (
        snapshot["gpu_poll_interval_ms"],
        snapshot["gpu_release_stabilization_ms"],
    )
    if observed_protocol != protocol:
        issues.append(_error(report, "$.policy", "GPU protocol differs from policy catalog"))
    if snapshot["candidates"] != _expected_candidates(policy, report):
        issues.append(_error(report, "$.policy.candidates", "differs from referenced policy"))
    classes = {item["id"] for item in cast(list[JsonObject], policy["hardware_classes"])}
    if report.data["hardware_class"] not in classes:
        issues.append(_error(report, "$.hardware_class", "not present in referenced policy"))
    return issues


def _resource_issues(document: Document, path: str, candidate: JsonObject) -> list[ValidationIssue]:
    """Recheck CUDA reserve, release, and internally consistent peak evidence."""
    if candidate["outcome"] != "valid":
        return []
    hardware = cast(JsonObject, document.data["hardware"])
    if hardware["backend"] != "cuda":
        return []
    policy = cast(JsonObject, document.data["policy"])
    minimum_free = float(cast(float, candidate["vram_min_free_gib"]))
    reserve = float(cast(float, policy["minimum_free_vram_gib"]))
    issues: list[ValidationIssue] = []
    if minimum_free < reserve:
        issues.append(_error(document, f"{path}.vram_min_free_gib", "violates policy reserve"))
    baseline = float(cast(float, candidate["vram_baseline_gib"]))
    release = float(cast(float, candidate["vram_release_used_gib"]))
    tolerance = float(cast(float, policy["vram_release_tolerance_gib"]))
    if release > baseline + tolerance:
        field = f"{path}.vram_release_used_gib"
        issues.append(_error(document, field, "exceeds release tolerance"))
    peak = float(cast(float, candidate["vram_peak_gib"]))
    total = float(cast(float, hardware["vram_total_gib"]))
    if not isclose(peak + minimum_free, total, rel_tol=0.0, abs_tol=1e-9):
        issues.append(_error(document, path, "peak and minimum-free VRAM disagree with total"))
    return issues


def _winner(candidates: list[JsonObject], backend: str) -> str | None:
    """Recompute the packaged report winner from valid measured candidates only."""
    valid = [
        (index, value) for index, value in enumerate(candidates) if value["outcome"] == "valid"
    ]
    if not valid:
        return None

    def key(item: tuple[int, JsonObject]) -> tuple[float, float, int]:
        """Build the normative median, headroom, and prudent-order key."""
        index, candidate = item
        rates = cast(JsonObject, candidate["tok_s"])
        free = inf if backend == "cpu" else float(cast(float, candidate["vram_min_free_gib"]))
        return float(cast(float, rates["median"])), free, -index

    return cast(str, max(valid, key=key)[1]["id"])


def _mode_selection_issues(
    document: Document, mode_id: str, mode: JsonObject
) -> list[ValidationIssue]:
    """Validate resource evidence and any accepted deterministic selection for one mode."""
    candidates = cast(list[JsonObject], mode["candidates"])
    base = f"$.modes.{mode_id}.candidates"
    issues: list[ValidationIssue] = []
    for index, candidate in enumerate(candidates):
        issues.extend(_resource_issues(document, f"{base}[{index}]", candidate))
    if document.data["decision"] != "accepted":
        return issues
    if mode["selected_candidate_id"] != _winner(candidates, _backend(document)):
        path = f"$.modes.{mode_id}.selected_candidate_id"
        issues.append(_error(document, path, "does not follow the deterministic selection rule"))
    return issues


def _selection_issues(document: Document) -> list[ValidationIssue]:
    """Validate the measured evidence and deterministic selection of every report mode."""
    issues: list[ValidationIssue] = []
    for mode_id, mode in cast(JsonObject, document.data["modes"]).items():
        issues.extend(_mode_selection_issues(document, mode_id, cast(JsonObject, mode)))
    return issues


def _report_class_issues(
    document: Document, policies: dict[str, JsonObject]
) -> list[ValidationIssue]:
    """Require accepted evidence to name a policy class containing its measured capacities."""
    if document.data["decision"] != "accepted":
        return []
    policy_id = cast(JsonObject, document.data["policy"])["id"]
    class_id = document.data["hardware_class"]
    issues: list[ValidationIssue] = []
    if policy_id is None:
        message = "accepted reports require an approved policy"
        issues.append(_error(document, "$.policy.id", message))
    if class_id is None:
        message = "accepted reports require a policy class"
        issues.append(_error(document, "$.hardware_class", message))
    policy = policies.get(cast(str, policy_id)) if policy_id is not None else None
    if policy is None or class_id is None:
        return issues
    classes = cast(list[JsonObject], policy["hardware_classes"])
    hardware_class = next((item for item in classes if item["id"] == class_id), None)
    if hardware_class is None:
        return issues
    hardware = cast(JsonObject, document.data["hardware"])
    ram_total = float(cast(float, hardware["ram_total_gib"]))
    if not _contains(hardware_class["ram_gib"], ram_total):
        message = "outside the named policy class"
        issues.append(_error(document, "$.hardware.ram_total_gib", message))
    vram = hardware["vram_total_gib"]
    if vram is not None and not _contains(hardware_class["vram_gib"], float(cast(float, vram))):
        message = "outside the named policy class"
        issues.append(_error(document, "$.hardware.vram_total_gib", message))
    return issues


def validate_calibration_content(
    documents: tuple[Document, ...], mode_ids: set[str]
) -> list[ValidationIssue]:
    """Validate every packaged calibration policy, report, and report-to-policy reference."""
    policies = index_policies(documents)
    protocol = _gpu_protocol(documents)
    issues: list[ValidationIssue] = []
    for document in documents:
        schema = document.data.get("schema")
        if schema == "calibration-policy/v1":
            issues.extend(_policy_issues(document, mode_ids))
        elif schema == "calibration-report/v1":
            issues.extend(_report_issues(document, mode_ids))
            issues.extend(_link_issues(document, policies, protocol))
            issues.extend(_report_class_issues(document, policies))
            issues.extend(_selection_issues(document))
    return issues
