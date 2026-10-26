"""Models: `extra=forbid`, frozen, discriminated union round-trip."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from witness.models import FsEvent, FsOp, MarkerRead, Record


def test_extra_forbid_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        MarkerRead(peer_pid=1, peer_exe="x", something_else="leak")  # type: ignore[call-arg]


def test_frozen_rejects_mutation() -> None:
    rec = MarkerRead(peer_pid=1, peer_exe="x")
    with pytest.raises(ValidationError):
        rec.peer_pid = 2  # type: ignore[misc]


def test_model_copy_produces_new_instance() -> None:
    rec = MarkerRead(peer_pid=1, peer_exe="x")
    updated = rec.model_copy(update={"seq": 5})
    assert updated.seq == 5
    assert rec.seq == -1  # original untouched


def test_digest_pattern_rejects_bad_hex() -> None:
    with pytest.raises(ValidationError):
        FsEvent(op=FsOp.create, path="a.txt", protected=False, sha256="not-hex")


def test_relpath_rejects_newline() -> None:
    with pytest.raises(ValidationError):
        FsEvent(op=FsOp.create, path="a\nb.txt", protected=False)


def test_discriminated_union_round_trip() -> None:
    adapter: TypeAdapter[Record] = TypeAdapter(Record)
    rec = MarkerRead(seq=0, peer_pid=1, peer_exe="x")
    payload = rec.model_dump_json()
    parsed = adapter.validate_json(payload)
    assert isinstance(parsed, MarkerRead)
    assert parsed.peer_pid == 1


def test_discriminated_union_rejects_unknown_kind() -> None:
    adapter: TypeAdapter[Record] = TypeAdapter(Record)
    with pytest.raises(ValidationError):
        adapter.validate_python({"seq": 0, "kind": "not_a_real_kind"})
