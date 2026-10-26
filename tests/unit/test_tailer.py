"""Tailer: rotation by inode, partial lines, truncation; pure parse helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path

from witness.models import AssistantClaim, TailMeta
from witness.tailer import Tailer, parse_json_output, parse_session_line


def _wait_for(events: list, predicate, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for e in events:
            if predicate(e):
                return e
        time.sleep(0.02)
    raise AssertionError(f"predicate never matched; saw {events}")


def test_parse_session_line_valid() -> None:
    line = json.dumps({"tool": "write", "paths": ["a.txt"], "count": 1}).encode()
    claim = parse_session_line(line)
    assert isinstance(claim, AssistantClaim)
    assert claim.claimed_paths == ["a.txt"]
    assert claim.tool.value == "write"


def test_parse_session_line_invalid_json_returns_none() -> None:
    assert parse_session_line(b"{not json") is None


def test_parse_session_line_empty_returns_none() -> None:
    assert parse_session_line(b"") is None
    assert parse_session_line(b"   \n") is None


def test_parse_json_output_multiple_actions() -> None:
    obj = {
        "actions": [
            {"tool": "write", "paths": ["a.txt"]},
            {"tool": "http", "hosts": ["x:1"]},
            {"tool": "not_a_real_tool"},  # dropped, invalid enum
        ]
    }
    claims = parse_json_output(obj)
    assert len(claims) == 2


def test_tailer_basic_line(tmp_path: Path) -> None:
    f = tmp_path / "session.log"
    f.write_text("")
    events: list = []
    tailer = Tailer([f])
    tailer.start(lambda rec: events.append(rec))
    try:
        with open(f, "a") as fh:
            fh.write(json.dumps({"tool": "write", "paths": ["x.txt"]}) + "\n")
        claim = _wait_for(events, lambda e: isinstance(e, AssistantClaim))
        assert claim.claimed_paths == ["x.txt"]
    finally:
        tailer.stop()


def test_tailer_partial_line_then_completed(tmp_path: Path) -> None:
    f = tmp_path / "session.log"
    f.write_text("")
    events: list = []
    tailer = Tailer([f])
    tailer.start(lambda rec: events.append(rec))
    try:
        partial = json.dumps({"tool": "write", "paths": ["y.txt"]})
        with open(f, "a") as fh:
            fh.write(partial[:10])  # no newline yet — partial
        time.sleep(0.3)
        assert not any(isinstance(e, AssistantClaim) for e in events)
        with open(f, "a") as fh:
            fh.write(partial[10:] + "\n")
        claim = _wait_for(events, lambda e: isinstance(e, AssistantClaim))
        assert claim.claimed_paths == ["y.txt"]
    finally:
        tailer.stop()


def test_tailer_rotation_by_inode(tmp_path: Path) -> None:
    f = tmp_path / "session.log"
    f.write_text(json.dumps({"tool": "write", "paths": ["first.txt"]}) + "\n")
    events: list = []
    tailer = Tailer([f])
    tailer.start(lambda rec: events.append(rec))
    try:
        _wait_for(
            events, lambda e: isinstance(e, AssistantClaim) and e.claimed_paths == ["first.txt"]
        )

        # Rotate: replace the file with a new inode.
        f.unlink()
        f.write_text(json.dumps({"tool": "write", "paths": ["second.txt"]}) + "\n")

        _wait_for(events, lambda e: isinstance(e, TailMeta) and e.event == "rotate")
        _wait_for(
            events, lambda e: isinstance(e, AssistantClaim) and e.claimed_paths == ["second.txt"]
        )
    finally:
        tailer.stop()


def test_tailer_truncate(tmp_path: Path) -> None:
    f = tmp_path / "session.log"
    f.write_text(json.dumps({"tool": "write", "paths": ["big.txt"]}) + "\n" * 1)
    events: list = []
    tailer = Tailer([f])
    tailer.start(lambda rec: events.append(rec))
    try:
        _wait_for(events, lambda e: isinstance(e, AssistantClaim))
        with open(f, "r+") as fh:
            fh.truncate(0)
        _wait_for(events, lambda e: isinstance(e, TailMeta) and e.event == "truncate")
    finally:
        tailer.stop()
