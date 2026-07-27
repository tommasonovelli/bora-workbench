"""Test release lookup, checksum-verified download, and uv handoff without any network.

Every HTTPS call is replaced by a fake so the suite stays offline (specification section 5.12).
The tests cover what an update must never get wrong: it must not downgrade, must not install bytes
whose digest does not match the release manifest, and must not follow a redirect off HTTPS.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

import bora_workbench.update as update

REPO_ROOT = Path(__file__).resolve().parents[1]
WHEEL = update.wheel_name("0.3.0")


class FakeResponse:
    """Stand in for the two response shapes the update module reads."""

    def __init__(self, payload: object) -> None:
        """Hold one payload served either as text, bytes, or decoded JSON."""
        self.payload = payload

    @property
    def text(self) -> str:
        """Return the manifest body."""
        return str(self.payload)

    @property
    def content(self) -> bytes:
        """Return the wheel body."""
        assert isinstance(self.payload, bytes)
        return self.payload

    def json(self) -> object:
        """Return the already-decoded GitHub release payload."""
        return self.payload


def _wheel_bytes(engine_release: str | None = "b10011") -> bytes:
    """Build a minimal wheel-shaped zip that optionally carries a packaged engine lock."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("bora_workbench/__init__.py", "")
        if engine_release is not None:
            lock = json.dumps({"release": engine_release})
            archive.writestr("bora_workbench/resources/engine.lock", lock)
    return stream.getvalue()


def _serve(monkeypatch, responses: dict[str, object]) -> list[str]:
    """Replace HTTPS access with an exact URL-to-payload table and record every request."""
    requested: list[str] = []

    def fake_get(url: str) -> FakeResponse:
        """Return the payload registered for one exact URL, or a 404-shaped failure."""
        requested.append(url)
        if url not in responses:
            raise update.UpdateError(f"{url} returned HTTP 404")
        return FakeResponse(responses[url])

    monkeypatch.setattr(update, "_https_get", fake_get)
    return requested


def _release_urls(version: str, wheel: bytes) -> dict[str, object]:
    """Build a consistent latest-release, manifest, and wheel table for one version."""
    digest = hashlib.sha256(wheel).hexdigest()
    base = f"{update._DOWNLOAD_BASE}/v{version}"
    return {
        update._LATEST_RELEASE_URL: {"tag_name": f"v{version}"},
        f"{base}/SHA256SUMS": f"{digest}  {update.wheel_name(version)}\n",
        f"{base}/{update.wheel_name(version)}": wheel,
    }


def test_only_a_strictly_newer_release_is_an_update() -> None:
    """Compare releases numerically so 0.2.10 outranks 0.2.9 and equality is not an update."""
    assert update.is_newer("0.2.10", "0.2.9")
    assert not update.is_newer("0.2.2", "0.2.2")
    assert not update.is_newer("0.2.1", "0.2.2")


def test_a_version_outside_major_minor_patch_is_refused() -> None:
    """Refuse an unparsable version instead of guessing an order for it."""
    with pytest.raises(update.UpdateError, match=r"major\.minor\.patch"):
        update.release_order("0.3.0rc1")


def test_latest_version_reads_the_published_tag(monkeypatch) -> None:
    """Read the newest published release tag, which excludes drafts and prereleases."""
    _serve(monkeypatch, {update._LATEST_RELEASE_URL: {"tag_name": "v0.3.0"}})

    assert update.latest_version() == "0.3.0"


def test_a_release_without_a_version_tag_is_actionable(monkeypatch) -> None:
    """Refuse a release whose tag is missing rather than constructing a download URL from it."""
    _serve(monkeypatch, {update._LATEST_RELEASE_URL: {"name": "untagged"}})

    with pytest.raises(update.UpdateError, match=r"vX\.Y\.Z tag"):
        update.latest_version()


def test_download_stores_only_bytes_matching_the_release_manifest(tmp_path, monkeypatch) -> None:
    """Verify the manifest digest before the wheel reaches its final cache path."""
    wheel = _wheel_bytes()
    _serve(monkeypatch, _release_urls("0.3.0", wheel))

    stored = update.download_wheel("0.3.0", tmp_path)

    assert stored == tmp_path / "updates" / WHEEL
    assert stored.read_bytes() == wheel


def test_download_refuses_a_checksum_mismatch_and_leaves_no_artifact(tmp_path, monkeypatch) -> None:
    """Never install bytes the release manifest does not vouch for (section 5.10)."""
    responses = _release_urls("0.3.0", _wheel_bytes())
    responses[f"{update._DOWNLOAD_BASE}/v0.3.0/{WHEEL}"] = b"tampered"
    _serve(monkeypatch, responses)

    with pytest.raises(update.UpdateError, match="checksum mismatch"):
        update.download_wheel("0.3.0", tmp_path)

    assert not (tmp_path / "updates" / WHEEL).exists()


def test_download_refuses_a_manifest_without_the_wheel(tmp_path, monkeypatch) -> None:
    """Treat a manifest that omits the wheel as a failure, not as an unverified download."""
    responses = _release_urls("0.3.0", _wheel_bytes())
    responses[f"{update._DOWNLOAD_BASE}/v0.3.0/SHA256SUMS"] = "abc  install.sh\n"
    _serve(monkeypatch, responses)

    with pytest.raises(update.UpdateError, match="does not list"):
        update.download_wheel("0.3.0", tmp_path)


def test_manifest_digest_must_be_sixty_four_hexadecimal_characters() -> None:
    """Refuse a malformed digest instead of comparing the wheel against nonsense."""
    with pytest.raises(update.UpdateError, match="malformed digest"):
        update._expected_digest(f"not-a-digest  {WHEEL}\n", WHEEL)


def test_a_redirect_off_https_is_refused(monkeypatch) -> None:
    """Keep TLS mandatory across every hop the release download follows (section 5.12)."""
    request = httpx.Request("GET", "https://example.invalid/start")
    hop = httpx.Response(302, request=httpx.Request("GET", "http://example.invalid/plain"))
    monkeypatch.setattr(
        update.httpx, "get", lambda *a, **k: httpx.Response(200, request=request, history=[hop])
    )

    with pytest.raises(update.UpdateError, match="away from HTTPS"):
        update._https_get("https://example.invalid/start")


def test_a_transport_failure_names_the_unreachable_url(monkeypatch) -> None:
    """Report an unreachable release API as an actionable error without a traceback."""

    def fail(*args, **kwargs) -> httpx.Response:
        """Simulate a transport failure before any response exists."""
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(update.httpx, "get", fail)

    with pytest.raises(update.UpdateError, match="cannot reach"):
        update._https_get("https://example.invalid/start")


def test_the_pinned_engine_release_is_read_from_the_downloaded_wheel(tmp_path) -> None:
    """Answer whether the update also needs `bora engine install` from the wheel's own lock."""
    wheel = tmp_path / WHEEL
    wheel.write_bytes(_wheel_bytes("b10011"))

    assert update.pinned_engine_release(wheel) == "b10011"


def test_an_unreadable_lock_reduces_the_engine_report_to_unknown(tmp_path) -> None:
    """Keep a verified update usable when its packaged lock cannot be inspected."""
    wheel = tmp_path / WHEEL
    wheel.write_bytes(_wheel_bytes(None))

    assert update.pinned_engine_release(wheel) is None
    assert update.pinned_engine_release(tmp_path / "absent.whl") is None


def test_the_scheduled_uv_command_installs_exactly_the_verified_wheel(monkeypatch) -> None:
    """Hand uv a forced install of the verified wheel on the pinned interpreter."""
    scheduled: list[tuple[str, ...]] = []
    monkeypatch.setattr(update, "schedule_uv_command", lambda _i, args: scheduled.append(args))

    update.schedule_tool_update(update.ToolInstallation(Path("env"), Path("uv")), Path("w.whl"))

    assert scheduled == [("tool", "install", "--force", "--python", update.PYTHON_VERSION, "w.whl")]


def test_the_update_python_pin_matches_both_installers() -> None:
    """Keep the interpreter an update installs identical to the one the installers pin."""
    expected = update.PYTHON_VERSION
    assert f'PYTHON_VERSION="{expected}"' in (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    assert f"$PythonVersion = '{expected}'" in (REPO_ROOT / "install.ps1").read_text(
        encoding="utf-8"
    )
