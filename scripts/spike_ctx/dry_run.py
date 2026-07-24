"""Exercise the spike package against the repository's offline fake server."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from qwen_launcher._calibration_vram import VramReserveError
from scripts.spike_ctx.quick import QuickRequest, run_quick
from scripts.spike_ctx.search import find_boundary


def _free_port() -> int:
    """Reserve and release one loopback port for the offline fake dry-run."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_until_ready(port: int) -> None:
    """Wait briefly for the local fake health endpoint without external traffic."""
    for _ in range(100):
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.1)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.01)
    raise RuntimeError("offline fake server did not become ready")


def _write_manifest(root: Path) -> None:
    """Hash dry-run output except the manifest itself."""
    files = sorted(path for path in root.rglob("*") if path.is_file())
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}"
        for path in files
        if path.name != "SHA256SUMS"
    ]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _probe(value: int) -> BaseException | None:
    """Expose a deterministic n_cpu_moe=37 boundary through real outcome classes."""
    return None if value >= 37 else VramReserveError("dry-run reserve")


def run_dry(output_root: Path) -> None:
    """Exercise HTTP timing parsing, bisection, and output against the fake server."""
    output_root.mkdir(parents=True, exist_ok=False)
    port = _free_port()
    fake = Path(__file__).parents[2] / "tests/fakes/fake_server.py"
    process = subprocess.Popen([sys.executable, str(fake), "--port", str(port)])
    try:
        _wait_until_ready(port)
        quick = run_quick(QuickRequest(f"http://127.0.0.1:{port}", output_root / "responses"))
    finally:
        process.terminate()
        process.wait(timeout=5)
    document = {
        "schema": "cross-context-spike-dry-run/v1",
        "quick": asdict(quick),
        "search": asdict(find_boundary(_probe)),
    }
    path = output_root / "results.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    _write_manifest(output_root)
