"""FsWatcher: create/modify/delete; protected flag; polling fallback."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from witness.listeners.fswatch import FsWatcher
from witness.models import FsEvent, FsOp


def _wait_for(events: list[FsEvent], predicate, timeout: float = 2.0) -> FsEvent:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for e in events:
            if predicate(e):
                return e
        time.sleep(0.02)
    raise AssertionError(f"predicate never matched within {timeout}s; saw: {events}")


@pytest.mark.parametrize("force_polling", [False, True])
def test_create_and_protected_flag(tmp_path: Path, force_polling: bool) -> None:
    (tmp_path / "protected").mkdir()
    events: list[FsEvent] = []
    watcher = FsWatcher(tmp_path, ["protected"], force_polling=force_polling)
    watcher.start(lambda rec: events.append(rec))
    try:
        (tmp_path / "protected" / "secret_file").write_bytes(b"content")
        ev = _wait_for(events, lambda e: e.path.endswith("secret_file") and e.op == FsOp.create)
        assert ev.protected is True

        (tmp_path / "ordinary.txt").write_bytes(b"hi")
        ev2 = _wait_for(events, lambda e: e.path == "ordinary.txt" and e.op == FsOp.create)
        assert ev2.protected is False
    finally:
        watcher.stop()


def test_modify_and_delete(tmp_path: Path) -> None:
    events: list[FsEvent] = []
    watcher = FsWatcher(tmp_path, ["protected"])
    watcher.start(lambda rec: events.append(rec))
    try:
        f = tmp_path / "a.txt"
        f.write_bytes(b"one")
        _wait_for(events, lambda e: e.path == "a.txt" and e.op == FsOp.create)
        f.write_bytes(b"one-modified")
        _wait_for(events, lambda e: e.path == "a.txt" and e.op == FsOp.modify)
        f.unlink()
        _wait_for(events, lambda e: e.path == "a.txt" and e.op == FsOp.delete)
    finally:
        watcher.stop()


def test_hash_matches_content(tmp_path: Path) -> None:
    import hashlib

    events: list[FsEvent] = []
    watcher = FsWatcher(tmp_path, ["protected"])
    watcher.start(lambda rec: events.append(rec))
    try:
        content = b"hello hash world"
        (tmp_path / "h.txt").write_bytes(content)
        ev = _wait_for(events, lambda e: e.path == "h.txt" and e.op == FsOp.create)
        assert ev.sha256 == hashlib.sha256(content).hexdigest()
        assert ev.bytes == len(content)
    finally:
        watcher.stop()
