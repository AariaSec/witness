"""Persistence-detection timing (final-plan patch #1).

A denied/EPERM write is invisible to a file watcher, so the fix uses a
*writable* lab path under a protected prefix instead: the file CREATE
itself is the finding trigger, and the stop action fires off that
creation directly (no second round trip waiting for a write-denial that
will never come). This test drives the real pipeline — FsWatcher -> bus
-> ledger -> detectors -> ActionRunner -> stop_pgroup on a real child
process — and asserts the full create-to-stop latency is under 500ms,
matching the final-plan's own verification claim ("5/5 recorded runs").
"""

from __future__ import annotations

import contextlib
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from witness.actions import ActionRunner
from witness.actions.receipt import Signer
from witness.bus import EventBus
from witness.detectors import DetectorState
from witness.detectors import evaluate as detectors_evaluate
from witness.ledger import Ledger
from witness.listeners.fswatch import FsWatcher
from witness.listeners.marker import MarkerService
from witness.models import ActionResult, Finding, FindingKind


def _drive_one_persistence_run(tmp_path: Path, trial: int) -> float:
    """Returns elapsed seconds from file creation to a successful
    stop_pgroup ActionResult for the resulting protected_write Finding."""
    lab = tmp_path / f"lab{trial}"
    protected_dir = lab / "protected"
    protected_dir.mkdir(parents=True)

    marker = MarkerService(f"WITNESS-DECOY-{trial:08x}", port=0)
    marker.start(lambda rec: None)

    child = subprocess.Popen(["sleep", "30"], preexec_fn=os.setsid)
    pgid = os.getpgid(child.pid)

    bus = EventBus()
    fswatcher = FsWatcher(lab, ["protected"])
    fswatcher.start(bus.emit_fn)

    ledger = Ledger(tmp_path / f"ledger{trial}.jsonl")
    signer = Signer.load_or_create(tmp_path / "keys")
    action_runner = ActionRunner(marker, pgid, ledger, signer)
    state_box = [DetectorState()]
    stop_action_time: list[float] = []

    def on_append(rec: object) -> None:
        state_box[0], findings = detectors_evaluate(state_box[0], rec)  # type: ignore[arg-type]
        for finding in findings:
            assert isinstance(finding, Finding)
            appended = ledger.append(finding)
            assert isinstance(appended, Finding)
            if appended.fkind == FindingKind.protected_write:
                results = action_runner.handle(appended)
                for r in results:
                    assert isinstance(r, ActionResult)
                    if r.action == "stop_pgroup" and r.ok:
                        stop_action_time.append(time.monotonic())

    ledger.on_append(on_append)

    stop_consumer = threading.Event()

    def consume() -> None:
        while not stop_consumer.is_set():
            try:
                rec = bus.get(timeout=0.05)
            except queue.Empty:
                continue
            ledger.append(rec)

    consumer_thread = threading.Thread(target=consume, daemon=True)
    consumer_thread.start()

    try:
        t_create = time.monotonic()
        (protected_dir / "config_backup").write_bytes(b"persistence attempt\n")

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not stop_action_time:
            time.sleep(0.005)

        assert stop_action_time, "protected_write finding + stop_pgroup never fired within 2s"
        elapsed = stop_action_time[0] - t_create
        return elapsed
    finally:
        stop_consumer.set()
        consumer_thread.join(timeout=2.0)
        fswatcher.stop()
        marker.stop()
        ledger.close()
        if child.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pgid, 9)
        child.wait(timeout=5)


def test_protected_write_create_to_stop_under_500ms(tmp_path: Path) -> None:
    elapsed = _drive_one_persistence_run(tmp_path, 0)
    assert elapsed < 0.5, f"create-to-stop latency was {elapsed * 1000:.1f}ms, budget is 500ms"


def test_protected_write_create_to_stop_under_500ms_5_of_5(tmp_path: Path) -> None:
    """Mirrors the final-plan's own "verified within 500ms on 5/5 recorded
    runs" claim — re-measure it here rather than trust the prose."""
    elapsed_ms = []
    for trial in range(5):
        elapsed = _drive_one_persistence_run(tmp_path, trial + 1)
        elapsed_ms.append(elapsed * 1000)
        assert elapsed < 0.5, f"trial {trial}: {elapsed * 1000:.1f}ms exceeded 500ms budget"
    print(f"\npersistence-detection create-to-stop latency over 5 runs (ms): {elapsed_ms}")
