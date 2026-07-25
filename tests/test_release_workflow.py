"""Test release workflow immutability and least-privilege publication."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"


def test_release_actions_are_pinned_to_full_commit_shas() -> None:
    """Require every release action reference to use an immutable 40-hex commit."""
    text = WORKFLOW.read_text(encoding="utf-8")
    action_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("uses:")]

    assert len(action_lines) == 7
    assert all(re.search(r"@[0-9a-f]{40}(?:\s+#\s+\S+)?$", line) for line in action_lines)


def test_release_triggers_on_v_prefixed_version_tags() -> None:
    """Pin the `vx.y.z` tag convention that the build job compares to the package version."""
    text = WORKFLOW.read_text(encoding="utf-8")

    assert '- "v*"' in text
    assert 'test "v${version}" = "${GITHUB_REF_NAME}"' in text


def test_publish_job_uses_tested_artifact_oidc_and_protected_environment() -> None:
    """Keep opt-in OIDC publication confined to the job consuming the tested build."""
    text = WORKFLOW.read_text(encoding="utf-8")
    prefix, publish = text.split("\n  publish:\n", maxsplit=1)

    assert "permissions:\n  contents: read" in prefix
    assert "needs: build" in publish
    assert "vars.PYPI_PUBLISH_ENABLED == 'true'" in publish
    assert "name: pypi" in publish
    assert "id-token: write" in publish
    assert "actions/download-artifact@" in publish
    assert "pypa/gh-action-pypi-publish@" in publish
    assert "password:" not in text
    assert "workflow_dispatch" not in text
