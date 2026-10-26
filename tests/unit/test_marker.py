"""Marker service: 200 + decoy, 410 after close, loopback-only bind."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from witness.listeners.marker import MarkerService
from witness.models import MarkerRead


def test_rejects_non_loopback_bind() -> None:
    with pytest.raises(ValueError):
        MarkerService("WITNESS-DECOY-aaaaaaaa", host="0.0.0.0")


def test_serves_decoy_then_410_after_close() -> None:
    events: list[MarkerRead] = []
    svc = MarkerService("WITNESS-DECOY-aaaaaaaa", port=0)
    svc.start(lambda rec: events.append(rec))
    try:
        url = f"http://127.0.0.1:{svc.bound_port}/v1/token"
        with urllib.request.urlopen(url, timeout=2) as resp:
            assert resp.status == 200
            body = json.loads(resp.read())
            assert body["decoy_value"] == "WITNESS-DECOY-aaaaaaaa"
            assert body["token_type"] == "decoy_key"

        svc.close_token()

        try:
            urllib.request.urlopen(url, timeout=2)
            raised = False
        except urllib.error.HTTPError as exc:
            raised = True
            assert exc.code == 410
        assert raised
    finally:
        svc.stop()

    assert len(events) == 2
    assert all(isinstance(e, MarkerRead) for e in events)


def test_unknown_path_is_404() -> None:
    svc = MarkerService("WITNESS-DECOY-bbbbbbbb", port=0)
    svc.start(lambda rec: None)
    try:
        url = f"http://127.0.0.1:{svc.bound_port}/not-a-real-path"
        try:
            urllib.request.urlopen(url, timeout=2)
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        svc.stop()
