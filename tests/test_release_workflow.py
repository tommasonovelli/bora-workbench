"""Test release workflow immutability and GitHub-only publication."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"


def test_release_actions_are_pinned_to_full_commit_shas() -> None:
    """Require every release action reference to use an immutable 40-hex commit."""
    text = WORKFLOW.read_text(encoding="utf-8")
    action_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("uses:")]

    assert len(action_lines) == 5
    assert all(re.search(r"@[0-9a-f]{40}(?:\s+#\s+\S+)?$", line) for line in action_lines)


def test_release_triggers_on_v_prefixed_version_tags() -> None:
    """Pin the `vx.y.z` tag convention that the build job compares to the package version."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert '- "v*"' in text
    assert 'test "v${version}" = "${GITHUB_REF_NAME}"' in text


def test_release_has_no_registry_publication_path() -> None:
    """Keep the release trigger and artifacts limited to GitHub Releases."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in text
    assert "workflow_dispatch:" not in text
    assert "id-token: write" not in text
    assert "actions/download-artifact@" not in text
    assert "python-package-distributions" not in text
    assert "pypi" not in text.casefold()


def test_build_verifies_uninstall_and_uploads_digest_bundle() -> None:
    """Bundle the tested distributions, installers, and digests for GitHub."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python scripts/verify_uninstall.py" in text
    assert "name: bora-workbench-release-bundle" in text
    assert "sha256sum" in text
    assert "install.sh" in text
    assert "install.ps1" in text
    assert "SHA256SUMS" in text
