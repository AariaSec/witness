"""Fuzz: `witness.claude_journal`'s pure parse functions must never raise on
arbitrary bytes/objects, and anything they emit must validate against its
pydantic model — same invariant `test_muse_journal_fuzz.py` and
`test_tailer_fuzz.py` hold their own formats to."""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from witness.claude_journal import ClaudeCodeClaimParser, claim_from_record

_byte_lines = st.binary(min_size=0, max_size=4096)
_json_values = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text()),
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(max_size=20), children, max_size=5),
    ),
    max_leaves=20,
)


@given(st.dictionaries(st.text(max_size=20), _json_values, max_size=10))
@settings(max_examples=300)
def test_claim_from_record_never_raises(rec: dict) -> None:
    result = claim_from_record(rec)
    assert result is None or result.model_dump() is not None


@given(_byte_lines, st.sampled_from(["session_log", "json_output"]))
@settings(max_examples=300)
def test_parser_parse_line_never_raises(data: bytes, source: str) -> None:
    parser = ClaudeCodeClaimParser()
    result = parser.parse_line(data, source)
    assert isinstance(result, list)
    for rec in result:
        assert rec.model_dump() is not None


@given(st.text(max_size=4096))
@settings(max_examples=100)
def test_parser_parse_line_never_raises_on_arbitrary_text(data: str) -> None:
    parser = ClaudeCodeClaimParser()
    result = parser.parse_line(data.encode("utf-8", errors="ignore"), "session_log")
    assert isinstance(result, list)


def test_claim_from_record_handles_non_dict_input() -> None:
    assert claim_from_record(None) is None  # type: ignore[arg-type]
    assert claim_from_record([1, 2, 3]) is None  # type: ignore[arg-type]
    assert claim_from_record("a string") is None  # type: ignore[arg-type]


def test_claim_from_record_handles_huge_structured_patch_without_raising() -> None:
    rec = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "x"}],
        },
        "toolUseResult": {
            "type": "create",
            "filePath": "x" * 10_000,  # oversized; must be truncated, never raise
            "structuredPatch": [{"a": 1}] * 10_000,
        },
    }
    claim = claim_from_record(rec)
    assert claim is not None
    assert len(claim.claimed_paths[0]) == 256
    assert claim.claimed_count == 10_000


def test_parser_oversized_line_never_raises() -> None:
    parser = ClaudeCodeClaimParser()
    huge = json.dumps({"type": "user", "pad": "a" * (3 * 1024 * 1024)}).encode()
    out = parser.parse_line(huge, "session_log")
    assert isinstance(out, list)
