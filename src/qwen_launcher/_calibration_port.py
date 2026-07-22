"""Select loopback ports for isolated calibration trial servers."""

from __future__ import annotations

import socket

from qwen_launcher._process_health import port_is_available


def select_trial_port(preferred_port: int) -> int:
    """Use the configured port when free, otherwise ask the OS for a temporary loopback port."""
    if port_is_available(preferred_port):
        return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
