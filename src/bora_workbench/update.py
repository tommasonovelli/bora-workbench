"""Find, verify, and schedule the installation of a newer published bora-workbench release.

Distribution is GitHub Releases only (D-070), so an update is exactly what the documented manual
installation does: read the newest published tag, fetch the wheel and the release `SHA256SUMS`,
refuse anything whose digest does not match, and hand the verified wheel to uv. The download rules
of specification section 5.10 apply unchanged: HTTPS throughout, a mandatory SHA-256, and an atomic
same-directory write.

The managed engine is deliberately untouched. It lives under the data root and is selected by
`engine.lock`, so replacing the Python tool leaves it installed and active; this module only reads
the new wheel's lock to report whether `bora engine install` is now required (D-073).
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

import httpx

from bora_workbench._tool_handoff import ToolInstallation, schedule_uv_command

_REPOSITORY = "tommasonovelli/bora-workbench"
_LATEST_RELEASE_URL = f"https://api.github.com/repos/{_REPOSITORY}/releases/latest"
_DOWNLOAD_BASE = f"https://github.com/{_REPOSITORY}/releases/download"
_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "bora-workbench"}
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Every published release carries the pinned interpreter of the installers, so an update must not
# silently move the tool to another Python (specification section 5.1).
PYTHON_VERSION = "3.12.13"

# The wheel is the only artifact an update installs, and the release manifest names it exactly.
_LOCK_IN_WHEEL = "bora_workbench/resources/engine.lock"
_RELEASE_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_HEX_64 = re.compile(r"[0-9a-f]{64}")


class UpdateError(RuntimeError):
    """Signal an actionable update failure mapped to exit code 1 without a traceback."""


def wheel_name(version: str) -> str:
    """Return the wheel file name the release workflow publishes for one version."""
    return f"bora_workbench-{version}-py3-none-any.whl"


def release_order(version: str) -> tuple[int, int, int]:
    """Order one strict `major.minor.patch` version, which is the only form ever published."""
    match = _RELEASE_VERSION.fullmatch(version)
    if match is None:
        raise UpdateError(f"unsupported version {version!r}; expected major.minor.patch")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def is_newer(candidate: str, installed: str) -> bool:
    """Report whether the candidate is strictly newer, so an update never downgrades."""
    return release_order(candidate) > release_order(installed)


def _https_get(url: str) -> httpx.Response:
    """Fetch one URL, refusing any hop that leaves HTTPS (specification section 5.10)."""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=_TIMEOUT, headers=_HEADERS)
    except httpx.HTTPError as error:
        raise UpdateError(f"cannot reach {url}: {error}") from error
    for hop in (*response.history, response):
        if hop.url.scheme != "https":
            raise UpdateError(f"refusing a request redirected away from HTTPS: {hop.url}")
    if response.status_code != 200:
        raise UpdateError(f"{url} returned HTTP {response.status_code}")
    return response


def latest_version() -> str:
    """Return the version of the newest published release, excluding drafts and prereleases."""
    response = _https_get(_LATEST_RELEASE_URL)
    try:
        payload = response.json()
    except ValueError as error:
        raise UpdateError(f"the GitHub release API returned unreadable JSON: {error}") from error
    tag = payload.get("tag_name") if isinstance(payload, dict) else None
    if not isinstance(tag, str) or not tag.startswith("v"):
        raise UpdateError("the latest GitHub Release does not publish a vX.Y.Z tag")
    version = tag[1:]
    release_order(version)
    return version


def _expected_digest(manifest: str, filename: str) -> str:
    """Return the SHA-256 the release manifest records for one exact file name."""
    for line in manifest.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename:
            if _HEX_64.fullmatch(parts[0]) is None:
                raise UpdateError(f"SHA256SUMS records a malformed digest for {filename}")
            return parts[0]
    raise UpdateError(f"SHA256SUMS does not list {filename}")


def _store(payload: bytes, directory: Path, filename: str) -> Path:
    """Write verified bytes with an atomic same-directory replace (section 5.10)."""
    partial = directory / f".{filename}.part"
    target = directory / filename
    try:
        directory.mkdir(parents=True, exist_ok=True)
        partial.write_bytes(payload)
        partial.replace(target)
    except OSError as error:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"cannot store the downloaded wheel: {error}") from error
    return target


def download_wheel(version: str, cache_root: Path) -> Path:
    """Return the release wheel in the managed cache after verifying its manifest digest."""
    if cache_root.is_symlink():
        raise UpdateError(f"managed cache root must not be a symlink: {cache_root}")
    filename = wheel_name(version)
    base = f"{_DOWNLOAD_BASE}/v{version}"
    expected = _expected_digest(_https_get(f"{base}/SHA256SUMS").text, filename)
    payload = _https_get(f"{base}/{filename}").content
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        raise UpdateError(f"checksum mismatch for {filename}: expected {expected}, got {digest}")
    return _store(payload, cache_root / "updates", filename)


def pinned_engine_release(wheel: Path) -> str | None:
    """Return the engine release the downloaded wheel pins, or None when it cannot be read.

    The answer only decides whether the update also requires `bora engine install`, so an
    unreadable lock reduces the report to advice instead of failing a verified update.
    """
    try:
        with zipfile.ZipFile(wheel) as archive:
            lock = json.loads(archive.read(_LOCK_IN_WHEEL))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None
    release = lock.get("release") if isinstance(lock, dict) else None
    return release if isinstance(release, str) else None


def schedule_tool_update(installation: ToolInstallation, wheel: Path) -> None:
    """Install the verified wheel with uv once this process releases its own environment."""
    arguments = ("tool", "install", "--force", "--python", PYTHON_VERSION, str(wheel))
    schedule_uv_command(installation, arguments)
