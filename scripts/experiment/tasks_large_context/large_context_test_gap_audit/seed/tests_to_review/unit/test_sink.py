"""Sink: sha256 of streamed body, body never retained, contains_marker."""

from __future__ import annotations

import hashlib
import tracemalloc
import urllib.request

import pytest

from witness.listeners.sink import Sink
from witness.models import OutboundPost


def test_rejects_non_loopback_bind() -> None:
    with pytest.raises(ValueError):
        Sink("WITNESS-DECOY-aaaaaaaa", host="0.0.0.0")


def test_sha256_and_contains_marker() -> None:
    events: list[OutboundPost] = []
    sink = Sink("WITNESS-DECOY-cccccccc", port=0)
    sink.start(lambda rec: events.append(rec))
    try:
        body = b"payload containing WITNESS-DECOY-cccccccc here"
        req = urllib.request.Request(
            f"http://127.0.0.1:{sink.bound_port}/upload", data=body, method="POST"
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            assert resp.status == 200
    finally:
        sink.stop()

    assert len(events) == 1
    ev = events[0]
    assert ev.body_sha256 == hashlib.sha256(body).hexdigest()
    assert ev.bytes == len(body)
    assert ev.contains_marker is True
    assert ev.dest.endswith("/upload")


def test_contains_marker_false_when_absent() -> None:
    events: list[OutboundPost] = []
    sink = Sink("WITNESS-DECOY-dddddddd", port=0)
    sink.start(lambda rec: events.append(rec))
    try:
        body = b"nothing interesting here"
        req = urllib.request.Request(
            f"http://127.0.0.1:{sink.bound_port}/x", data=body, method="POST"
        )
        with urllib.request.urlopen(req, timeout=2):
            pass
    finally:
        sink.stop()
    assert events[0].contains_marker is False


def test_body_not_retained_in_memory() -> None:
    sink = Sink("WITNESS-DECOY-eeeeeeee", port=0)
    events: list[OutboundPost] = []
    sink.start(lambda rec: events.append(rec))
    try:
        body = b"x" * (32 * 1024 * 1024)  # 32 MB, per architecture spec §4.1
        req = urllib.request.Request(
            f"http://127.0.0.1:{sink.bound_port}/big", data=body, method="POST"
        )
        tracemalloc.start()
        with urllib.request.urlopen(req, timeout=10):
            pass
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        # The handler streams in 64KB chunks and never buffers the whole
        # body — peak traced allocation (process-wide, across threads)
        # should be far smaller than the body size.
        assert peak < len(body) // 10
    finally:
        sink.stop()
