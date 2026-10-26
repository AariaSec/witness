"""Digest-only POST sink — the decoy exfiltration destination.

Streams the request body in fixed-size chunks to compute a sha256 digest
and a byte count, and to check (substring match, on the chunk stream) for
the decoy marker value. The body itself is never buffered in full and
never retained: each chunk is hashed and discarded immediately.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer

import psutil
from pydantic import BaseModel

from witness.models import OutboundPost

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_CHUNK = 64 * 1024


def _content_type_enum(header: str | None) -> str:
    if not header:
        return "other"
    header = header.lower()
    if "json" in header:
        return "json"
    if "form" in header:
        return "form"
    if "text" in header:
        return "text"
    if "octet-stream" in header or "binary" in header:
        return "binary"
    return "other"


def _find_peer(remote_port: int) -> tuple[int | None, str | None]:
    try:
        for proc in psutil.process_iter(["pid"]):
            try:
                conns = proc.net_connections(kind="inet")
            except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                continue
            for c in conns:
                if c.laddr and c.laddr.port == remote_port:
                    try:
                        return proc.pid, proc.name()
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        return proc.pid, None
    except (psutil.AccessDenied, psutil.Error):
        return None, None
    return None, None


class Sink:
    """`EventSource` accepting `POST /*` and emitting digest-only records."""

    def __init__(
        self,
        decoy_value: str,
        port: int = 47102,
        max_bytes: int = 64 * 2**20,
        host: str = "127.0.0.1",
    ) -> None:
        if host not in _LOOPBACK_HOSTS:
            raise ValueError(f"Sink must bind to loopback only, got {host!r}")
        self._decoy_bytes = decoy_value.encode("utf-8")
        self._host = host
        self._requested_port = port
        self._max_bytes = max_bytes
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._emit: Callable[[BaseModel], None] | None = None

    @property
    def bound_port(self) -> int:
        if self._server is None:
            return self._requested_port
        return int(self._server.server_address[1])

    def start(self, emit: Callable[[BaseModel], None]) -> None:
        self._emit = emit
        service = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt: str, *args: object) -> None:
                return

            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length", 0) or 0)
                length = min(length, service._max_bytes)
                remaining = length
                hasher = None
                import hashlib

                hasher = hashlib.sha256()
                total = 0
                # Track a short tail across chunk boundaries so the decoy
                # substring check isn't defeated by an unlucky split.
                marker = service._decoy_bytes
                tail = b""
                found_marker = False
                while remaining > 0:
                    chunk = self.rfile.read(min(_CHUNK, remaining))
                    if not chunk:
                        break
                    hasher.update(chunk)
                    total += len(chunk)
                    remaining -= len(chunk)
                    window = tail + chunk
                    if marker and marker in window:
                        found_marker = True
                    tail = window[-(len(marker) - 1):] if len(marker) > 1 else b""
                    del chunk, window  # drop references promptly

                content_type = _content_type_enum(self.headers.get("Content-Type"))
                peer_pid, peer_exe = _find_peer(self.client_address[1])

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                body = b'{"status":"ok"}'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

                if service._emit is not None:
                    service._emit(
                        OutboundPost(
                            peer_pid=peer_pid,
                            peer_exe=peer_exe,
                            dest=f"{service._host}:{service.bound_port}{self.path}",
                            bytes=total,
                            body_sha256=hasher.hexdigest(),
                            content_type=content_type,  # type: ignore[arg-type]
                            contains_marker=found_marker,
                        )
                    )

            def do_POST(self) -> None:
                self._handle()

            def do_PUT(self) -> None:
                self._handle()

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


__all__ = ["Sink"]
