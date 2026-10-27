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


def test_contains_marker_true_only_when_decoy_value_present(tmp_path: Path) -> None:
    events: list[FsEvent] = []
    watcher = FsWatcher(tmp_path, ["protected"], decoy_value="WITNESS-DECOY-abc123")
    watcher.start(lambda rec: events.append(rec))
    try:
        (tmp_path / "clean.txt").write_bytes(b"ordinary content, nothing here")
        clean = _wait_for(events, lambda e: e.path == "clean.txt" and e.op == FsOp.create)
        assert clean.contains_marker is False

        (tmp_path / "leaked.json").write_bytes(b'{"token": "WITNESS-DECOY-abc123"}')
        leaked = _wait_for(events, lambda e: e.path == "leaked.json" and e.op == FsOp.create)
        assert leaked.contains_marker is True

        # A similar-but-not-equal value must not false-positive.
        (tmp_path / "similar.json").write_bytes(b'{"token": "WITNESS-DECOY-abc124"}')
        similar = _wait_for(events, lambda e: e.path == "similar.json" and e.op == FsOp.create)
        assert similar.contains_marker is False
    finally:
        watcher.stop()


def test_contains_marker_is_none_without_decoy_value_configured(tmp_path: Path) -> None:
    """No decoy_value supplied (e.g. a non-decoy-aware caller) -> never
    silently reports False; stays None, same as an unread file."""
    events: list[FsEvent] = []
    watcher = FsWatcher(tmp_path, ["protected"])
    watcher.start(lambda rec: events.append(rec))
    try:
        (tmp_path / "x.txt").write_bytes(b"anything")
        ev = _wait_for(events, lambda e: e.path == "x.txt" and e.op == FsOp.create)
        assert ev.contains_marker is None
    finally:
        watcher.stop()
