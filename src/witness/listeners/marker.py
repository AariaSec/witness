"""Decoy marker HTTP service.

Serves a decoy credential value — always called a "decoy key"/"decoy
value" in any user-facing string, never phrased as if it were real — via
a small credential-provider-shaped URI: `GET /v1/token`. Any read is a
strong signal the assistant (or something it spawned) is probing for
credentials; the detector for this is `detectors/marker_read.py`.

Binds loopback ONLY. This mirrors the AariaSec proxy's RULE 3 posture:
there is no sanctioned non-loopback mode for this service at all.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer

import psutil
from pydantic import BaseModel

from witness.canon import sha256_hex
from witness.models import MarkerRead

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _find_peer(remote_port: int) -> tuple[int | None, str | None]:
    """Best-effort match of a TCP client's ephemeral port to a local pid.
    Degrades silently (returns `(None, None)`) when the OS denies access —
    this is expected and documented (see failure-mode table: `AccessDenied`
    -> continue, detection still works via marker/sink alone)."""
    try:
        for proc in psutil.process_iter(["pid"]):
            try:
                conns = proc.net_connections(kind="inet")
            except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                continue
            for c in conns:
                if c.laddr and c.laddr.port == remote_port:
                    exe = None
                    try:
                        exe = proc.name()
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        exe = None
                    return proc.pid, exe
    except (psutil.AccessDenied, psutil.Error):
        return None, None
    return None, None


class MarkerService:
    """`EventSource` serving a decoy marker value at `GET /v1/token`."""

    def __init__(self, decoy_value: str, port: int = 47101, host: str = "127.0.0.1") -> None:
        if host not in _LOOPBACK_HOSTS:
            raise ValueError(f"MarkerService must bind to loopback only, got {host!r}")
        self._decoy_value = decoy_value
        self._host = host
        self._requested_port = port
        self._closed = threading.Event()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._emit: Callable[[BaseModel], None] | None = None

    @property
    def bound_port(self) -> int:
        if self._server is None:
            return self._requested_port
        return int(self._server.server_address[1])

    def close_token(self) -> None:
        """After this call, GET /v1/token serves 410 Gone."""
        self._closed.set()

    def start(self, emit: Callable[[BaseModel], None]) -> None:
        self._emit = emit
        service = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt: str, *args: object) -> None:
                return  # never log to stdout — no incidental content capture

            def do_GET(self) -> None:
                if self.path != "/v1/token":
                    self.send_response(404)
                    self.end_headers()
                    return

                peer_pid, peer_exe = _find_peer(self.client_address[1])
                ua = self.headers.get("User-Agent")
                ua_digest = sha256_hex(ua.encode("utf-8")) if ua else None

                if service._closed.is_set():
                    self.send_response(410)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":"gone"}')
                else:
                    body = json.dumps(
                        {
                            "token_type": "decoy_key",
                            "decoy_value": service._decoy_value,
                            "uri": "witness://decoy-credential-provider/v1/token",
                        }
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                if service._emit is not None:
                    service._emit(
                        MarkerRead(peer_pid=peer_pid, peer_exe=peer_exe, ua_digest=ua_digest)
                    )

        try:
            self._server = HTTPServer((self._host, self._requested_port), Handler)
        except OSError:
            self._server = HTTPServer((self._host, 0), Handler)

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


__all__ = ["MarkerService"]
