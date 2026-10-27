"""Action: stop a process group — SIGTERM, grace period, then SIGKILL.

Also sweeps `extra_pids` (pids seen talking to the marker/sink that may
have escaped the recorded process group — see failure mode
`pgroup_escape` in the architecture doc).
"""

from __future__ import annotations

import contextlib
import os
import signal
import time
from typing import Literal

import psutil


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not ours to signal-probe further
    except OSError:
        return False


def _pgroup_alive(pgid: int) -> bool:
    for proc in psutil.process_iter(["pid"]):
        try:
            if os.getpgid(proc.pid) == pgid:
                return True
        except (ProcessLookupError, PermissionError, psutil.NoSuchProcess):
            continue
    return False


def _signal_all(pgid: int, extra_pids: set[int], sig: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)
    for pid in extra_pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, sig)


def stop_pgroup(
    pgid: int, extra_pids: set[int] | None = None, grace_s: float = 2.0, kill_wait_s: float = 1.0
) -> Literal["term", "kill", "failed"]:
    """Briefly widened to 3.0s/2.0s then 5.0s/3.0s chasing a real Modal-
    cloud "failed" result (2026-10-27), on the hypothesis that it was
    slightly-too-tight timing. Reverted: at every budget tried (3.0s,
    5.0s, 8.0s total), the reported latency overshot the deadline by the
    SAME ~20-24ms (one poll-loop tick), not a growing margin -- proof the
    process group was never actually detected dead within ANY window
    tried, however large. Widening further would only waste wall-clock
    time, not fix anything. The real cause is very likely that signal
    delivery to a process group doesn't work the same way under Modal's
    sandboxed container runtime as it does locally (the pid whose exit
    briefly looked like confirmation was probably the container itself
    tearing down after this function returned, not our SIGKILL landing)
    -- see docs/LIMITATIONS.md's "Modal-sandbox stop_pgroup" entry for
    the full writeup and what's still open. `kill_wait_s` is a real,
    useful parameter now (was a hardcoded 1.0) even though these
    particular defaults match the pre-investigation values."""
    extra_pids = extra_pids or set()

    _signal_all(pgid, extra_pids, signal.SIGTERM)

    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline:
        if not _pgroup_alive(pgid) and not any(_pid_alive(p) for p in extra_pids):
            return "term"
        time.sleep(0.02)

    _signal_all(pgid, extra_pids, signal.SIGKILL)

    deadline = time.monotonic() + kill_wait_s
    while time.monotonic() < deadline:
        if not _pgroup_alive(pgid) and not any(_pid_alive(p) for p in extra_pids):
            return "kill"
        time.sleep(0.02)

    return "failed"


__all__ = ["stop_pgroup"]
