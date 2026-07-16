"""Offline fake HTTP server for deterministic lifecycle and health-contract tests."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeServer(ThreadingHTTPServer):
    """Hold mutable health request count for delayed-readiness behavior."""

    health_mode: str
    delayed_requests: int
    health_requests: int


class Handler(BaseHTTPRequestHandler):
    """Serve the locked health shape and a minimal models endpoint."""

    server: FakeServer

    def _send_json(self, status: int, value: object) -> None:
        """Write one deterministic UTF-8 JSON response."""
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Respond with ready, delayed, loading, or incompatible health data."""
        if self.path == "/v1/models":
            self._send_json(200, {"data": []})
            return
        if self.path == "/":
            self._send_json(200, {"interface": "fake integrated UI"})
            return
        if self.path != "/health":
            self._send_json(404, {"error": "not found"})
            return
        self.server.health_requests += 1
        mode = self.server.health_mode
        if mode == "loading":
            self._send_json(503, {"error": {"message": "Loading model"}})
        elif mode == "incompatible":
            self._send_json(200, {"status": "unexpected"})
        elif mode == "delayed" and self.server.health_requests <= self.server.delayed_requests:
            self._send_json(503, {"error": {"message": "Loading model"}})
        else:
            self._send_json(200, {"status": "ok"})

    def log_message(self, format: str, *args: object) -> None:
        """Keep fake process logs stable and free of request timestamps."""
        del format, args


def _arguments() -> argparse.Namespace:
    """Parse only fake controls, never real llama.cpp options."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument(
        "--health-mode",
        choices=("ready", "delayed", "loading", "incompatible", "crash"),
        default="ready",
    )
    parser.add_argument("--delayed-requests", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    """Run on loopback until terminated, or exit immediately for crash simulation."""
    arguments = _arguments()
    if arguments.health_mode == "crash":
        raise SystemExit(9)
    server = FakeServer(("127.0.0.1", arguments.port), Handler)
    server.health_mode = arguments.health_mode
    server.delayed_requests = arguments.delayed_requests
    server.health_requests = 0
    server.serve_forever()


if __name__ == "__main__":
    main()
