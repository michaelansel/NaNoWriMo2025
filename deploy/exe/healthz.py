#!/usr/bin/env python3
"""Tiny health endpoint for the exe.dev self-hosted GitHub Actions runner.

Answers ``GET /healthz`` with 200 and ``{"runner": "active"}`` only while the
GitHub Actions runner systemd service is active, otherwise 503. The hosted
``probe`` job in the workflows curls this URL to decide whether AI jobs can be
scheduled on the ``exe`` runner or must post an "unavailable" comment instead.

Runs as a systemd unit (see ``nano-healthz.service``) bound to the VM's
platform port, which exe.dev exposes as ``https://<vm>.exe.xyz/``.
"""

from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("HEALTHZ_PORT", "8000"))
RUNNER_UNIT_GLOB = os.environ.get("RUNNER_UNIT_GLOB", "actions.runner.*.service")


def runner_active() -> bool:
    """Return True when any GitHub Actions runner unit is active."""
    try:
        out = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=active",
             "--no-legend", "--plain", RUNNER_UNIT_GLOB],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return any(line.strip() for line in out.splitlines())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path.rstrip("/") not in ("", "/healthz"):
            self.send_error(404)
            return
        active = runner_active()
        body = json.dumps({"runner": "active" if active else "inactive"}).encode()
        self.send_response(200 if active else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        return  # keep journal quiet; systemd captures errors


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
