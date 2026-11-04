"""Filesystem watcher: watchdog native backend with a polling fallback.

Persistence-detection fix (final-plan patch #1): a denied/EPERM write is
invisible to a file watcher, so the "protected write" scenario uses a
*writable* lab path under one of `protected_paths` instead. Any `create`
under a protected path is flagged `protected=True` on the `FsEvent`; the
`protected_write` detector treats that creation itself as the finding
trigger (no need to ever see a permission failure). The native backend
(FSEvents on macOS, inotify on Linux) is what keeps this fast enough for
the <500ms create-to-stop budget; the polling fallback uses a short
0.1s tick for the same reason, in case inotify watch limits are hit.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.observers.polling import PollingObserver

from witness.canon import sha256_hex
from witness.models import FsEvent, FsOp


class FsWatcher:
    """`EventSource` watching `lab` recursively for create/modify/delete/move."""

    def __init__(
        self,
        lab: Path,
        protected: list[str],
        hash_limit: int = 8 * 2**20,
        force_polling: bool = False,
    ) -> None:
        self._lab = Path(lab).resolve()
        self._protected = [p.strip("/") for p in protected]
        self._hash_limit = hash_limit
        self._force_polling = force_polling or bool(os.environ.get("WITNESS_FORCE_POLLING_FS"))
        self._emit: Callable[[BaseModel], None] | None = None
        self._observer: BaseObserver | None = None
        self.degraded = False

    def _relpath(self, abspath: str) -> str:
        try:
            rel = os.path.relpath(abspath, self._lab)
        except ValueError:
            rel = abspath
        return rel[:256]

    def _is_protected(self, relpath: str) -> bool:
        return any(relpath == p or relpath.startswith(p + "/") for p in self._protected)

    def _hash_and_size(self, abspath: str) -> tuple[int | None, str | None]:
        try:
            size = os.path.getsize(abspath)
        except OSError:
            return None, None
        if size > self._hash_limit:
            return size, None
        try:
            with open(abspath, "rb") as fh:
                data = fh.read()
            return size, sha256_hex(data)
        except OSError:
            return size, None

    def _handle(self, abspath: str, op: FsOp) -> None:
        relpath = self._relpath(abspath)
        protected = self._is_protected(relpath)
        if op in (FsOp.create, FsOp.modify):
            size, digest = self._hash_and_size(abspath)
        else:
            size, digest = None, None

        if self._emit is not None:
            self._emit(
                FsEvent(op=op, path=relpath, bytes=size, sha256=digest, protected=protected)
            )

    def start(self, emit: Callable[[BaseModel], None]) -> None:
        self._emit = emit
        watcher = self

        def _as_str(path: bytes | str) -> str:
            return path.decode("utf-8", errors="replace") if isinstance(path, bytes) else path

        class Handler(FileSystemEventHandler):
            def on_created(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                watcher._handle(_as_str(event.src_path), FsOp.create)

            def on_modified(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                watcher._handle(_as_str(event.src_path), FsOp.modify)

            def on_deleted(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                watcher._handle(_as_str(event.src_path), FsOp.delete)

            def on_moved(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                watcher._handle(_as_str(event.dest_path), FsOp.move)

        self._lab.mkdir(parents=True, exist_ok=True)

        if not self._force_polling:
            try:
                self._observer = Observer()
                self._observer.schedule(Handler(), str(self._lab), recursive=True)
                self._observer.start()
                return
            except OSError:
                self._observer = None

        self.degraded = True
        self._observer = PollingObserver(timeout=0.1)
        self._observer.schedule(Handler(), str(self._lab), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None


__all__ = ["FsWatcher"]
