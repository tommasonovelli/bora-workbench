"""Validate measured resource constraints and deterministic calibration selections."""

from __future__ import annotations

from math import inf, isclose
from typing import cast

from qwen_launcher.validation import Document, JsonObject, ValidationIssue


def _error(document: Document, path: str, message: str) -> ValidationIssue:
    """Create a report error tied to one measured or selected value."""
    return ValidationIssue("error", document.file, path, message)


def _contains(values: object, measurement: float) -> bool:
    """Return whether an exact measurement belongs to an inclusive policy range."""
    minimum, maximum = cast(list[float | None], values)
    return cast(float, minimum) <= measurement and (maximum is None or measurement <= maximum)


def _policy_catalog(documents: tuple[Document, ...]) -> dict[str, JsonObject]:
    """Index schema-valid calibration policies by identifier."""
    catalog: dict[str, JsonObject] = {}
    for document in documents:
        if document.data.get("schema") != "calibration-policy/v1":
            continue
        for policy in cast(list[JsonObject], document.data["policies"]):
            catalog[cast(str, policy["id"])] = policy
    return catalog


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
    """Recompute the calibration/v1 winner from valid measured candidates only."""
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


def _mode_issues(document: Document, mode_id: str, mode: JsonObject) -> list[ValidationIssue]:
    """Validate resource evidence and any accepted deterministic selection for one mode."""
    candidates = cast(list[JsonObject], mode["candidates"])
    base = f"$.modes.{mode_id}.candidates"
    issues: list[ValidationIssue] = []
    for index, candidate in enumerate(candidates):
        issues.extend(_resource_issues(document, f"{base}[{index}]", candidate))
    if document.data["decision"] != "accepted":
        return issues
    backend = cast(str, cast(JsonObject, document.data["hardware"])["backend"])
    if mode["selected_candidate_id"] != _winner(candidates, backend):
        path = f"$.modes.{mode_id}.selected_candidate_id"
        issues.append(_error(document, path, "does not follow the deterministic selection rule"))
    return issues


def _class_issues(document: Document, policies: dict[str, JsonObject]) -> list[ValidationIssue]:
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


def _search_issues(document: Document, policy_index: int) -> list[ValidationIssue]:
    """Reject policy searches that compare contexts or repeat equivalent envelopes."""
    policy = cast(list[JsonObject], document.data["policies"])[policy_index]
    backend = cast(str, policy["backend"])
    issues: list[ValidationIssue] = []
    for mode_id, raw_mode in cast(JsonObject, policy["modes"]).items():
        candidates = cast(list[JsonObject], cast(JsonObject, raw_mode)["candidates"])
        base = f"$.policies[{policy_index}].modes.{mode_id}.candidates"
        if len({candidate["ctx"] for candidate in candidates}) != 1:
            issues.append(_error(document, base, "must use one fixed context"))
        if backend == "cpu" and len(candidates) > 1:
            issues.append(_error(document, base, "CPU has no varying envelope at fixed context"))
        if backend != "cuda" or any("n_cpu_moe" not in item for item in candidates):
            continue
        values = [candidate["n_cpu_moe"] for candidate in candidates]
        if len(values) != len(set(values)):
            issues.append(_error(document, base, "must use unique n_cpu_moe values"))
        if values != sorted(values, reverse=True):
            issues.append(_error(document, base, "must be ordered from prudent to aggressive"))
    return issues


def validate_report_selections(documents: tuple[Document, ...]) -> list[ValidationIssue]:
    """Apply specification section 5.6 to every policy search and report claim."""
    policies = _policy_catalog(documents)
    issues: list[ValidationIssue] = []
    for document in documents:
        if document.data.get("schema") != "calibration-policy/v1":
            continue
        for index, _policy in enumerate(cast(list[JsonObject], document.data["policies"])):
            issues.extend(_search_issues(document, index))
    for document in documents:
        if document.data.get("schema") != "calibration-report/v1":
            continue
        modes = cast(JsonObject, document.data["modes"])
        for mode_id, mode in modes.items():
            issues.extend(_mode_issues(document, mode_id, cast(JsonObject, mode)))
        issues.extend(_class_issues(document, policies))
    return issues
