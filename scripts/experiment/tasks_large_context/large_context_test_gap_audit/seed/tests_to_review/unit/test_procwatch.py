"""ProcWatcher: spawn/exit events observed within 500ms, via real subprocesses."""

from __future__ import annotations

import os
import subprocess
import time

from witness.listeners.procwatch import ProcWatcher
from witness.models import ProcEvent, ProcOp


def test_spawn_and_exit_observed_within_budget() -> None:
    events: list[ProcEvent] = []
    proc = subprocess.Popen(["sleep", "0.6"], preexec_fn=os.setsid)
    pgid = os.getpgid(proc.pid)

    watcher = ProcWatcher(pgid, interval_s=0.05)
    watcher.start(lambda rec: events.append(rec))
    try:
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and not any(
            e.op == ProcOp.spawn and e.pid == proc.pid for e in events
        ):
            time.sleep(0.02)
        assert any(e.op == ProcOp.spawn and e.pid == proc.pid for e in events), (
            "spawn should be observed within 500ms"
        )

        proc.wait()
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and not any(
            e.op == ProcOp.exit and e.pid == proc.pid for e in events
        ):
            time.sleep(0.02)
        assert any(e.op == ProcOp.exit and e.pid == proc.pid for e in events)
    finally:
        watcher.stop()


def test_known_pids_tracks_group() -> None:
    proc = subprocess.Popen(["sleep", "0.4"], preexec_fn=os.setsid)
    pgid = os.getpgid(proc.pid)
    watcher = ProcWatcher(pgid, interval_s=0.05)
    watcher.start(lambda rec: None)
    try:
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and proc.pid not in watcher.known_pids():
            time.sleep(0.02)
        assert proc.pid in watcher.known_pids()
    finally:
        proc.wait()
        watcher.stop()
