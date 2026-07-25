"""Acceptance tests for the distributed calibration policy, evidence, and manual flow."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from bora_workbench._calibration_privacy import privacy_findings
from bora_workbench.profiles import load_catalog
from bora_workbench.resources import read_json, resource
from bora_workbench.validation import validate_resources

_REPORT_PATH = "content/calibrations/windows-11-rtx-2060-super-v3.json"
_MANIFEST = Path("evidence/calibration/windows-11-rtx-2060-super-v3/SHA256SUMS")


def test_packaged_policy_and_reference_evidence_are_valid() -> None:
    """Distribute one v3 method and report without any production profile/v1 envelope."""
    policy = read_json("content/calibration-policy.json")
    report = read_json(_REPORT_PATH)

    assert validate_resources().errors == ()
    assert policy["schema"] == "calibration-policy/v2"
    assert report["schema"] == "calibration-report/v2"
    assert not resource("content/profiles").is_dir()
    assert report["gate"] == {
        "local_result": "calibration-accepted",
        "overall_status": "gate-partial",
        "constants_validated_on_materially_different_hardware": False,
        "heterogeneous_hardware_follow_up": "open-non-blocking",
    }


def test_empirical_scope_is_exact_and_not_a_heterogeneous_claim() -> None:
    """Name the only real v3 hardware while leaving the heterogeneous follow-up open."""
    policy = read_json("content/calibration-policy.json")
    scope = policy["empirical_coverage"]["measured_scope"]  # type: ignore[index]

    assert scope == [
        {
            "evidence_id": "windows-11-rtx-2060-super-v3",
            "os_name": "windows",
            "os_version": "Windows 11 build 10.0.26200",
            "backend": "cuda",
            "gpu_name": "NVIDIA GeForce RTX 2060 SUPER",
            "vram_total_gib": 8.0,
            "ram_total_gib": 31.92,
        }
    ]
    assert (
        policy["empirical_coverage"][  # type: ignore[index]
            "constants_validated_on_materially_different_hardware"
        ]
        is False
    )


def test_policy_and_source_references_bind_exact_bytes() -> None:
    """Reproduce policy-to-report and report-to-source checksums from the checkout."""
    policy = read_json("content/calibration-policy.json")
    report_bytes = resource(_REPORT_PATH).read_bytes()
    reference = policy["evidence"][0]  # type: ignore[index]

    assert hashlib.sha256(report_bytes).hexdigest() == reference["sha256"]
    report = read_json(_REPORT_PATH)
    for source in report["source_references"]:
        path = Path(source["path"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]


def test_manifest_reproduces_every_public_reference() -> None:
    """Verify the checked-in SHA256SUMS without relying on platform-specific shell tools."""
    for line in _MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest


def test_installed_reference_never_becomes_a_launch_plan() -> None:
    """Keep the shared report descriptive: no remote envelope may reach the runtime catalog."""
    catalog = load_catalog()

    assert catalog.profiles == ()
    assert not hasattr(catalog, "calibration_seeds")
    assert [mode.id for mode in catalog.modes] == ["coding", "studio", "vstudio"]


def test_contribution_guide_keeps_publication_manual_and_checklisted() -> None:
    """Ship naming, validation, privacy, PR text, and explicit no-automation instructions."""
    guide = Path("docs/calibration.md").read_text(encoding="utf-8")
    normalized = " ".join(guide.split())
    template = Path(".github/pull_request_template.md").read_text(encoding="utf-8")

    for required in (
        "## Contributing new evidence",
        "Pull request checklist:",
        "bora validate",
        "privacy_reviewed",
        "performs no logins, uploads, commits, remote branches, issues, or pull requests",
    ):
        assert required in normalized
    assert "Ordering-only seed" in template


def test_shareable_public_files_pass_privacy_scan(tmp_path) -> None:
    """Reject local identity or private-path leaks across distributed evidence and guidance."""
    root = tmp_path / "shareable"
    names = (
        "src/bora_workbench/resources/content/calibration-policy.json",
        "src/bora_workbench/resources/content/calibrations/windows-11-rtx-2060-super-v3.json",
        "evidence/calibration/windows-11-rtx-2060-super-v3/README.md",
        "docs/calibration.md",
    )
    for name in names:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(name, destination)

    assert privacy_findings(root) == ()
