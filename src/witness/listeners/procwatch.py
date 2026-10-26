"""psutil-based process-group watcher.

Polls the assistant's process group every `interval_s` and emits
`ProcEvent` spawn/exit records. Command lines are hashed (never stored
raw); only the executable basename is kept. If the assistant manages to
detach from its own process group (e.g. by calling `setsid` itself), the
proc watcher will see the known pid vanish without a matching exit in its
own tree — that's the `pgroup_escape` signal, resolved by the marker/sink
continuing to see traffic from a pid no longer in `known_pids()`.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable

import psutil
from pydantic import BaseModel

from witness.models import ProcEvent, ProcOp


def _cmdline_digest(proc: psutil.Process) -> str | None:
    try:
        cmdline = proc.cmdline()
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None
    if not cmdline:
        return None
    joined = "\x00".join(cmdline).encode("utf-8", errors="replace")
    return hashlib.sha256(joined).hexdigest()


def _exe_basename(proc: psutil.Process) -> str | None:
    try:
        name = proc.name()
        return name
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None


def _pgroup_pids(pgid: int) -> set[int]:
    """Best-effort enumeration of pids belonging to process group `pgid`."""
    import os

    pids: set[int] = set()
    for proc in psutil.process_iter(["pid"]):
        try:
            if os.getpgid(proc.pid) == pgid:
                pids.add(proc.pid)
        except (ProcessLookupError, PermissionError, psutil.NoSuchProcess):
            continue
    return pids


class ProcWatcher:
    """`EventSource` polling a process group for spawn/exit events."""

    def __init__(self, pgid: int, interval_s: float = 0.25) -> None:
        self._pgid = pgid
        self._interval_s = interval_s
        self._known: dict[int, psutil.Process] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._emit: Callable[[BaseModel], None] | None = None

    def known_pids(self) -> set[int]:
        return set(self._known.keys())

    def start(self, emit: Callable[[BaseModel], None]) -> None:
        self._emit = emit
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._poll_once()
            self._stop_event.wait(self._interval_s)

    def _poll_once(self) -> None:
        current_pids = _pgroup_pids(self._pgid)
        known_pids = set(self._known.keys())

        for pid in current_pids - known_pids:
            try:
                proc = psutil.Process(pid)
            except psutil.NoSuchProcess:
                continue
            self._known[pid] = proc
            ppid = None
            try:
                ppid = proc.ppid()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                ppid = None
            self._emit_event(
                ProcEvent(
                    op=ProcOp.spawn,
                    pid=pid,
                    ppid=ppid,
                    exe=_exe_basename(proc),
                    cmdline_digest=_cmdline_digest(proc),
                )
            )

        for pid in known_pids - current_pids:
            exited_proc = self._known.pop(pid, None)
            self._emit_event(
                ProcEvent(
                    op=ProcOp.exit,
                    pid=pid,
                    ppid=None,
                    exe=_exe_basename(exited_proc) if exited_proc else None,
                    cmdline_digest=None,
                )
            )

    def _emit_event(self, event: ProcEvent) -> None:
        if self._emit is not None:
            self._emit(event)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


__all__ = ["ProcWatcher"]
