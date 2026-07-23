"""Smoke-test complete self-uninstall from an isolated uv tool installation."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_REPOSITORY = Path(__file__).resolve().parents[1]


def _wheel() -> Path:
    """Return the single built qwen-launcher wheel expected in ``dist``."""
    wheels = sorted((_REPOSITORY / "dist").glob("qwen_launcher-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one qwen-launcher wheel, found {len(wheels)}")
    return wheels[0]


def _isolated_environment(root: Path) -> dict[str, str]:
    """Confine tool and launcher roots while reusing only uv's already-populated cache."""
    environment = dict(os.environ)
    uv_cache = subprocess.run(
        ["uv", "cache", "dir"], capture_output=True, text=True, check=True
    ).stdout.strip()
    environment["UV_CACHE_DIR"] = uv_cache
    environment["UV_TOOL_DIR"] = str(root / "uv-tools")
    environment["UV_TOOL_BIN_DIR"] = str(root / "bin")
    environment["UV_PYTHON_DOWNLOADS"] = "never"
    environment["XDG_CONFIG_HOME"] = str(root / "config")
    environment["XDG_DATA_HOME"] = str(root / "data")
    environment["XDG_CACHE_HOME"] = str(root / "cache")
    environment["XDG_STATE_HOME"] = str(root / "state")
    environment["APPDATA"] = str(root / "appdata")
    environment["LOCALAPPDATA"] = str(root / "localappdata")
    return environment


def _run(command: list[str], environment: dict[str, str], *, input_text: str | None = None) -> None:
    """Run one smoke-test command and retain its output in any actionable failure."""
    result = subprocess.run(
        command,
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode:
        detail = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        raise RuntimeError(f"command failed with exit {result.returncode}: {command}\n{detail}")


def _wait_until_absent(path: Path) -> None:
    """Allow the post-exit helper a short bounded interval to finish uv removal."""
    deadline = time.monotonic() + 10
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if path.exists():
        raise RuntimeError(f"self-uninstall left managed path behind: {path}")


def main() -> None:
    """Install the wheel with isolated uv roots, uninstall once, and require no tool remains."""
    with tempfile.TemporaryDirectory(prefix="qwen-launcher-uninstall-") as temporary:
        root = Path(temporary)
        environment = _isolated_environment(root)
        _run(
            [
                "uv",
                "tool",
                "install",
                "--offline",
                "--python",
                str(Path(sys._base_executable).resolve()),
                str(_wheel()),
            ],
            environment,
        )
        suffix = ".exe" if os.name == "nt" else ""
        command = root / "bin" / f"qwen-launcher{suffix}"
        if not command.is_file():
            raise RuntimeError(f"uv did not create the qwen-launcher command: {command}")
        _run([str(command), "uninstall"], environment, input_text="y\n")
        _wait_until_absent(root / "uv-tools" / "qwen-launcher")
        _wait_until_absent(command)
    print("Complete uv-tool uninstall smoke test passed.")


if __name__ == "__main__":
    main()
