"""psutil-based process-group watcher.

Polls the assistant's process group every `interval_s` and emits
`ProcEvent` spawn/exit/escape records. Command lines are hashed (never
stored raw); only the executable basename is kept.

`pgroup_escape` has two distinct shapes, both handled here:

1. A known member of the group vanishes from the group (its `os.getpgid`
   no longer matches) but the pid is still alive — a live process that
   detached, not a process that exited. Caught in `_poll_once`'s
   known-pid-vanished branch.
2. A descendant is born *already* detached — e.g. a child that calls
   `setsid()` in its own `preexec_fn` before `exec`, so by the time any
   poller observes it, it already carries a foreign pgid and was never a
   member of the recorded group at all. This is the harder, more common
   real-world shape (see `witness.demo.sim_agent`'s `escape`/
   `escape_relay` scenarios) — caught by `_scan_for_foreign_descendants`,
   which walks `ppid` ancestry (not just pgid) against every pid this
   watcher has EVER known about, at any depth, so a multi-hop detach
   (child escapes, then spawns its own child) is still attributed to the
   original group.
"""

from __future__ import annotations

import hashlib
import os
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


def _safe_ppid(proc: psutil.Process) -> int | None:
    try:
        return proc.ppid()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return None


def _safe_pgid(pid: int) -> int | None:
    try:
        return os.getpgid(pid)
    except (ProcessLookupError, PermissionError, psutil.NoSuchProcess):
        return None


def _is_live_non_zombie(pid: int) -> bool:
    """`psutil.pid_exists` alone is not enough to tell "still running,
    just detached" apart from "exited but not yet reaped by its parent" —
    a zombie keeps its pid (and its old pgid) until reaped, so it would
    otherwise be misclassified as an escape rather than an ordinary exit.
    """
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _pgroup_pids(pgid: int) -> set[int]:
    """Best-effort enumeration of pids belonging to process group `pgid`."""
    pids: set[int] = set()
    for proc in psutil.process_iter(["pid"]):
        if _safe_pgid(proc.pid) == pgid:
            pids.add(proc.pid)
    return pids


class ProcWatcher:
    """`EventSource` polling a process group for spawn/exit/escape events."""

    def __init__(self, pgid: int, interval_s: float = 0.25) -> None:
        self._pgid = pgid
        self._interval_s = interval_s
        self._known: dict[int, psutil.Process] = {}
        # Every pid ever attributed to this group, including ones that have
        # since exited or escaped — ancestry lookups need the history, not
        # just the live set, since the parent half of an escape may have
        # already exited by the time its child is observed.
        self._ever_known: set[int] = {pgid}
        self._escaped: set[int] = set()
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
            self._ever_known.add(pid)
            self._emit_event(
                ProcEvent(
                    op=ProcOp.spawn,
                    pid=pid,
                    ppid=_safe_ppid(proc),
                    exe=_exe_basename(proc),
                    cmdline_digest=_cmdline_digest(proc),
                )
            )

        for pid in known_pids - current_pids:
            exited_proc = self._known.pop(pid, None)
            if exited_proc is not None and _is_live_non_zombie(pid):
                # Still alive, just no longer in this pgid — detached, not
                # exited.
                self._escaped.add(pid)
                self._emit_event(
                    ProcEvent(
                        op=ProcOp.escape,
                        pid=pid,
                        ppid=_safe_ppid(exited_proc),
                        exe=_exe_basename(exited_proc),
                        cmdline_digest=_cmdline_digest(exited_proc),
                    )
                )
            else:
                self._emit_event(
                    ProcEvent(
                        op=ProcOp.exit,
                        pid=pid,
                        ppid=None,
                        exe=_exe_basename(exited_proc) if exited_proc else None,
                        cmdline_digest=None,
                    )
                )

        self._scan_for_foreign_descendants()

    def _scan_for_foreign_descendants(self) -> None:
        """Find pids never caught above: born with a foreign pgid, so they
        never appeared in `_pgroup_pids(self._pgid)` at all. Attributed to
        this group by `ppid` ancestry, walking `_ever_known` (which this
        method itself grows) so a chain of detaches is followed to any
        depth in a single pass, oldest-ancestor-first by construction of
        `process_iter` never guaranteeing order — so this loops until a
        pass finds nothing new.
        """
        while True:
            found_new = False
            for proc in psutil.process_iter(["pid"]):
                pid = proc.pid
                if pid in self._ever_known or pid in self._escaped:
                    continue
                if not _is_live_non_zombie(pid):
                    continue  # a zombie isn't actively doing anything foreign
                ppid = _safe_ppid(proc)
                if ppid is None or ppid not in self._ever_known:
                    continue
                if _safe_pgid(pid) == self._pgid:
                    continue  # same group after all — ordinary spawn path handles it
                self._ever_known.add(pid)
                self._escaped.add(pid)
                found_new = True
                self._emit_event(
                    ProcEvent(
                        op=ProcOp.escape,
                        pid=pid,
                        ppid=ppid,
                        exe=_exe_basename(proc),
                        cmdline_digest=_cmdline_digest(proc),
                    )
                )
            if not found_new:
                return

    def _emit_event(self, event: ProcEvent) -> None:
        if self._emit is not None:
            self._emit(event)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


__all__ = ["ProcWatcher"]
