"""Models: `extra=forbid`, frozen, discriminated union round-trip."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from witness.models import (
    FsEvent,
    FsOp,
    MarkerRead,
    ReceiptBody,
    Record,
    Watcher,
    strip_receipt_body_v02_defaults,
)


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


def _minimal_receipt_body(**overrides: object) -> ReceiptBody:
    base = dict(
        run_id="r1",
        final_digest="0" * 64,
        records=1,
        findings={},
        stop_status="not_needed",
        policy_hash="0" * 64,
        signed_at=1.0,
        pubkey="abc",
    )
    base.update(overrides)
    return ReceiptBody(**base)  # type: ignore[arg-type]


def test_receipt_body_v02_fields_default_to_empty() -> None:
    """Every pre-v0.2 construction call site (every existing test, every
    existing receipt-signing call) keeps working unmodified — the four
    new fields are optional with content-free defaults."""
    body = _minimal_receipt_body()
    assert body.git_commit_sha is None
    assert body.git_tree_digest is None
    assert body.changed_file_digests == {}
    assert body.coverage == []


def test_receipt_body_v02_fields_construct_with_real_values() -> None:
    body = _minimal_receipt_body(
        git_commit_sha="a" * 40,
        git_tree_digest="b" * 64,
        changed_file_digests={"src/foo.py": "c" * 64},
        coverage=[Watcher.fs, Watcher.marker, Watcher.sink],
    )
    assert body.git_commit_sha == "a" * 40
    assert body.git_tree_digest == "b" * 64
    assert body.changed_file_digests == {"src/foo.py": "c" * 64}
    assert body.coverage == [Watcher.fs, Watcher.marker, Watcher.sink]


def test_receipt_body_rejects_bad_git_commit_sha() -> None:
    with pytest.raises(ValidationError):
        _minimal_receipt_body(git_commit_sha="not-a-sha")


def test_receipt_body_rejects_unknown_coverage_value() -> None:
    with pytest.raises(ValidationError):
        _minimal_receipt_body(coverage=["not_a_real_watcher"])


def test_receipt_body_still_frozen_and_extra_forbid() -> None:
    body = _minimal_receipt_body()
    with pytest.raises(ValidationError):
        body.coverage = [Watcher.fs]  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _minimal_receipt_body(not_a_real_field="leak")  # type: ignore[call-arg]


def test_canonical_payload_strips_at_default_v02_fields() -> None:
    """A pre-v0.2-shaped body (none of the new fields ever set) must
    produce EXACTLY the same canonical payload a receipt signed before
    these fields existed would have — otherwise every already-frozen
    receipt's signature/chain-digest would break on re-verification."""
    body = _minimal_receipt_body()
    payload = body.canonical_payload()
    for key in ("git_commit_sha", "git_tree_digest", "changed_file_digests", "coverage"):
        assert key not in payload


def test_canonical_payload_keeps_genuinely_set_v02_fields() -> None:
    body = _minimal_receipt_body(
        git_commit_sha="a" * 40,
        coverage=[Watcher.fs],
    )
    payload = body.canonical_payload()
    assert payload["git_commit_sha"] == "a" * 40
    assert payload["coverage"] == ["fs"]
    # Fields left at default are still stripped even when siblings aren't.
    assert "git_tree_digest" not in payload
    assert "changed_file_digests" not in payload


def test_strip_receipt_body_v02_defaults_is_idempotent_and_in_place() -> None:
    payload: dict[str, object] = {"run_id": "r1", "coverage": [], "git_commit_sha": None}
    result = strip_receipt_body_v02_defaults(payload)
    assert result is payload
    assert payload == {"run_id": "r1"}
    # Calling again on the already-stripped payload is a no-op.
    assert strip_receipt_body_v02_defaults(payload) == {"run_id": "r1"}
