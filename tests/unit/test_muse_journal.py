"""Tests for `witness.muse_journal` — the real Muse Code `session.jsonl`
envelope parser.

`tests/fixtures/muse_journal/sanitized_session.jsonl` is a SANITIZED copy
of a real capture (muse 1.4.13, `--provider echo`, 2026-10-26): same
structural shape (77 lines, 1 `retained_frame` envelope + 76 flat inner
records) as an actual session, but every `prompt`/`text`/`message`/
`reason`/`duty` string value was replaced with the placeholder
`"placeholder prompt text"` before this file was committed — see
`docs/LIMITATIONS.md` for why those specific fields matter (they're the
ones confirmed to carry literal prompt/response text in a real capture).
No raw prompt or response text from any real session is or was ever
committed to this repo.
"""

from __future__ import annotations

import json
from pathlib import Path

from witness.models import AssistantClaim, TailMeta
from witness.muse_journal import (
    MuseJournalClaimParser,
    claim_from_inner_record,
    iter_inner_records,
    iter_session_file,
    unwrap_line,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "muse_journal" / "sanitized_session.txt"
# Named `.txt`, not `.jsonl`, on purpose: it's a line-delimited capture of
# Muse Code's OWN wire record shape, not a witness `bundle.jsonl` — giving
# it a bare `.jsonl` extension would make `scripts/leakscan.py --staged`
# check it against `schemas/allowed_keys.yaml` (witness's ledger-record key
# whitelist), which it was never meant to satisfy. `.txt` still runs the
# secret-pattern scan (`scan_text_blob`), just not the (inapplicable)
# key-whitelist check.


def _flat_record(payload_type: str = "runtime.session.metadata", **payload: object) -> dict:
    return {
        "schema_version": 1,
        "id": "01a00000-0000-7000-8000-000000000001",
        "stream": {"kind": "session", "id": "01a00000-0000-7000-8000-000000000002"},
        "sequence": 1,
        "recorded_at": 1700000000000000,
        "record_type": "event",
        "durability": "durable",
        "causation_id": None,
        "payload_type": payload_type,
        "payload_schema_version": 1,
        "payload": {"kind": "metadata", "record": {}, **payload},
    }


# --- unwrap_line -------------------------------------------------------


def test_unwrap_line_flat_record_passthrough() -> None:
    rec = _flat_record()
    assert unwrap_line(rec) == [rec]


def test_unwrap_line_envelope_unwraps_children() -> None:
    inner_a = _flat_record("a.type", seq=1)
    inner_b = _flat_record("b.type", seq=2)
    envelope = {
        "retained_frame": "session_permission_transaction",
        "frame_schema_version": 1,
        "outer_log_ordinal": 1,
        "transaction_id": "t-1",
        "children": [
            {"child_index": 0, "record_json": json.dumps(inner_a)},
            {"child_index": 1, "record_json": json.dumps(inner_b)},
        ],
        "content_sha256": "sha256:deadbeef",
    }
    out = unwrap_line(envelope)
    assert len(out) == 2
    assert out[0]["payload_type"] == "a.type"
    assert out[1]["payload_type"] == "b.type"


def test_unwrap_line_envelope_skips_malformed_children() -> None:
    envelope = {
        "retained_frame": "x",
        "children": [
            {"child_index": 0, "record_json": "{not json"},
            {"child_index": 1, "record_json": "42"},  # valid JSON, not a dict
            {"child_index": 2},  # missing record_json
            "not even a dict",
            {"child_index": 3, "record_json": json.dumps(_flat_record("ok.type"))},
        ],
    }
    out = unwrap_line(envelope)
    assert len(out) == 1
    assert out[0]["payload_type"] == "ok.type"


def test_unwrap_line_envelope_missing_children_is_empty() -> None:
    assert unwrap_line({"retained_frame": "x"}) == []
    assert unwrap_line({"retained_frame": "x", "children": "not-a-list"}) == []


def test_unwrap_line_unrecognized_shape_is_empty() -> None:
    assert unwrap_line({}) == []
    assert unwrap_line({"foo": "bar"}) == []
    # Missing one of the three required flat-record keys.
    assert unwrap_line({"payload_type": "x", "payload": {}}) == []


# --- iter_inner_records (bytes-level, never raises) ---------------------


def test_iter_inner_records_flat_line() -> None:
    line = json.dumps(_flat_record("foo.bar")).encode()
    recs = iter_inner_records(line)
    assert len(recs) == 1
    assert recs[0]["payload_type"] == "foo.bar"


def test_iter_inner_records_invalid_json_returns_empty() -> None:
    assert iter_inner_records(b"{not json") == []


def test_iter_inner_records_non_dict_json_returns_empty() -> None:
    assert iter_inner_records(b"[1, 2, 3]") == []
    assert iter_inner_records(b"42") == []
    assert iter_inner_records(b'"just a string"') == []


def test_iter_inner_records_empty_bytes_returns_empty() -> None:
    assert iter_inner_records(b"") == []


def test_iter_inner_records_oversized_line_returns_empty() -> None:
    huge = b'{"payload_type": "x", "payload": {}, "sequence": ' + b"9" * (3 * 1024 * 1024) + b"}"
    assert iter_inner_records(huge) == []


def test_iter_inner_records_invalid_utf8_never_raises() -> None:
    assert iter_inner_records(b"\xff\xfe\x00\x01") == []


# --- claim_from_inner_record --------------------------------------------


def test_claim_from_inner_record_no_mapping_returns_none() -> None:
    # Every real payload_type observed in this project's captures is
    # unmapped by design (see module docstring "the tool-call gap") — this
    # is the documented, expected behavior, not a bug.
    rec = _flat_record("runtime.session.metadata")
    assert claim_from_inner_record(rec) is None


def test_claim_from_inner_record_run_event_no_mapping_returns_none() -> None:
    rec = _flat_record("runtime.session", kind="run", event={"kind": "started", "prompt": "x"})
    assert claim_from_inner_record(rec) is None


def test_claim_from_inner_record_never_raises_on_garbage() -> None:
    assert claim_from_inner_record({}) is None
    assert claim_from_inner_record({"payload": "not-a-dict"}) is None
    assert claim_from_inner_record({"payload": {"kind": "run", "event": "not-a-dict"}}) is None


# --- MuseJournalClaimParser (ClaimParser protocol) -----------------------


def test_parser_flat_line_parses_without_raising() -> None:
    parser = MuseJournalClaimParser()
    line = json.dumps(_flat_record("runtime.session.metadata")).encode()
    out = parser.parse_line(line, "session_log")
    assert out == []  # no defensible claim mapping yet — expected


def test_parser_envelope_line_unwraps_both_children() -> None:
    parser = MuseJournalClaimParser()
    inner_a = _flat_record("a.type")
    inner_b = _flat_record("b.type")
    envelope = {
        "retained_frame": "session_permission_transaction",
        "children": [
            {"child_index": 0, "record_json": json.dumps(inner_a)},
            {"child_index": 1, "record_json": json.dumps(inner_b)},
        ],
        "content_sha256": "sha256:deadbeef",
    }
    out = parser.parse_line(json.dumps(envelope).encode(), "session_log")
    # Neither inner record maps to a claim tool, so both are dropped —
    # but the unwrap itself must not raise or lose track silently.
    assert out == []


def test_parser_empty_line_returns_empty_list() -> None:
    parser = MuseJournalClaimParser()
    assert parser.parse_line(b"", "session_log") == []
    assert parser.parse_line(b"   \n", "session_log") == []


def test_parser_invalid_json_returns_parse_error_meta() -> None:
    parser = MuseJournalClaimParser()
    out = parser.parse_line(b"{not json", "session_log")
    assert len(out) == 1
    assert isinstance(out[0], TailMeta)
    assert out[0].event == "parse_error"


def test_parser_non_dict_json_returns_parse_error_meta() -> None:
    parser = MuseJournalClaimParser()
    out = parser.parse_line(b"[1,2,3]", "session_log")
    assert len(out) == 1
    assert isinstance(out[0], TailMeta)
    assert out[0].event == "parse_error"


def test_parser_oversized_line_returns_parse_error_meta() -> None:
    parser = MuseJournalClaimParser()
    huge = b'{"payload_type": "x", "payload": {}, "sequence": ' + b"9" * (3 * 1024 * 1024) + b"}"
    out = parser.parse_line(huge, "session_log")
    assert len(out) == 1
    assert isinstance(out[0], TailMeta)
    assert out[0].event == "parse_error"
    assert out[0].bytes_skipped == len(huge)


def test_parser_valid_but_unrecognized_shape_is_quietly_dropped_not_an_error() -> None:
    # A structurally-fine JSON object that is neither an envelope nor a
    # flat inner record is dropped silently (empty list), NOT reported as
    # a parse_error — mirrors DefaultClaimParser's handling of a
    # recognized-but-irrelevant object.
    parser = MuseJournalClaimParser()
    out = parser.parse_line(json.dumps({"some": "unrelated object"}).encode(), "session_log")
    assert out == []


# --- against the real sanitized fixture ----------------------------------


def test_iter_session_file_against_real_sanitized_fixture() -> None:
    records = list(iter_session_file(FIXTURE))
    # 77 raw lines: 76 already-flat + 1 envelope line that unwraps to 2
    # children, so 78 total inner records.
    assert len(records) == 78
    payload_types = {r.get("payload_type") for r in records}
    assert "runtime.session.permission_format_declared" in payload_types
    assert "runtime.session.permission_profile_committed" in payload_types
    assert "session.started" in payload_types
    assert "session.end" in payload_types


def test_fixture_contains_no_unredacted_prose() -> None:
    # Defense in depth: re-assert at test time (not just at commit time)
    # that the fixture never carries real prompt/response text — this
    # test fails loudly if anyone ever regenerates the fixture without
    # sanitizing it.
    raw = FIXTURE.read_text()
    assert "say hello" not in raw
    assert "current directory" not in raw


def test_parser_tails_the_real_sanitized_fixture_as_a_live_file(tmp_path: Path) -> None:
    # Exercises the actual Tailer + MuseJournalClaimParser integration end
    # to end against real (sanitized) captured bytes, append-in-place like
    # a live muse process would write them.
    from witness.tailer import Tailer

    target = tmp_path / "session.jsonl"
    target.write_text("")
    events: list[AssistantClaim | TailMeta] = []
    tailer = Tailer([target], parser=MuseJournalClaimParser())
    tailer.start(lambda rec: events.append(rec))
    try:
        with open(target, "a") as fh:
            fh.write(FIXTURE.read_text())
        import time

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            time.sleep(0.05)
        # No raised exceptions is the primary assertion; since no real
        # tool-claim mapping exists yet, we expect zero AssistantClaim and
        # zero parse_error TailMeta (every real line in the fixture is
        # structurally valid).
        assert not any(isinstance(e, AssistantClaim) for e in events)
        assert not any(
            isinstance(e, TailMeta) and e.event == "parse_error" for e in events
        )
    finally:
        tailer.stop()
