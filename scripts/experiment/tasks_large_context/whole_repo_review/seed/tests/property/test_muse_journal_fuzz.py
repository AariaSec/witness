"""Fuzz: `witness.muse_journal`'s pure parse functions must never raise on
arbitrary bytes, and anything they emit must validate against its pydantic
model — same invariant `test_tailer_fuzz.py` holds the simulated-agent
format to."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from witness.muse_journal import (
    MuseJournalClaimParser,
    claim_from_inner_record,
    iter_inner_records,
    unwrap_line,
)

_byte_lines = st.binary(min_size=0, max_size=4096)
_json_values = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text()),
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(max_size=20), children, max_size=5),
    ),
    max_leaves=20,
)


@given(_byte_lines)
@settings(max_examples=300)
def test_iter_inner_records_never_raises(data: bytes) -> None:
    result = iter_inner_records(data)
    assert isinstance(result, list)
    for rec in result:
        assert isinstance(rec, dict)


@given(st.dictionaries(st.text(max_size=20), _json_values, max_size=10))
@settings(max_examples=300)
def test_unwrap_line_never_raises(obj: dict) -> None:
    result = unwrap_line(obj)
    assert isinstance(result, list)


@given(st.dictionaries(st.text(max_size=20), _json_values, max_size=10))
@settings(max_examples=300)
def test_claim_from_inner_record_never_raises(rec: dict) -> None:
    result = claim_from_inner_record(rec)
    assert result is None or result.model_dump() is not None


@given(_byte_lines, st.sampled_from(["session_log", "json_output"]))
@settings(max_examples=300)
def test_parser_parse_line_never_raises(data: bytes, source: str) -> None:
    parser = MuseJournalClaimParser()
    result = parser.parse_line(data, source)
    assert isinstance(result, list)
    for rec in result:
        assert rec.model_dump() is not None


def test_iter_inner_records_handles_embedded_nul_and_huge_line() -> None:
    assert iter_inner_records(b"\x00\x00\x00") == []
    huge = (
        b'{"payload_type": "x", "payload": {}, "sequence": 1, "pad": "'
        + b"a" * (3 * 1024 * 1024)
        + b'"}'
    )
    # Should not raise, regardless of outcome.
    iter_inner_records(huge)


def test_unwrap_line_handles_deeply_nested_envelope_garbage() -> None:
    # An envelope whose children are themselves envelope-shaped strings —
    # must not recurse infinitely or raise; record_json is parsed exactly
    # once per child, never re-unwrapped.
    nested = {"retained_frame": "x", "retained_frame_inner": "y"}
    envelope = {
        "retained_frame": "outer",
        "children": [{"child_index": 0, "record_json": '{"retained_frame": "inner"}'}],
    }
    out = unwrap_line(envelope)
    # The child's inner object lacks payload_type/payload/sequence, so it's
    # returned as-is by unwrap (this function doesn't recurse into a
    # second envelope layer) — just confirm no raise and a list comes back.
    assert isinstance(out, list)
    assert unwrap_line(nested) == []
