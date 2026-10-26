"""Fuzz: the tailer's pure parse functions must never raise, and anything
they emit must validate against its pydantic model."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from witness.tailer import DefaultClaimParser, parse_json_output, parse_session_line

_byte_lines = st.binary(min_size=0, max_size=2048)


@given(_byte_lines)
@settings(max_examples=300)
def test_parse_session_line_never_raises(data: bytes) -> None:
    result = parse_session_line(data)
    assert result is None or result.model_dump() is not None


@given(st.binary(min_size=0, max_size=2048), st.sampled_from(["session_log", "json_output"]))
@settings(max_examples=300)
def test_default_claim_parser_never_raises(data: bytes, source: str) -> None:
    parser = DefaultClaimParser()
    result = parser.parse_line(data, source)
    assert result is None or result.model_dump() is not None


@given(st.one_of(st.dictionaries(st.text(), st.text()), st.lists(st.text()), st.none(), st.text()))
@settings(max_examples=200)
def test_parse_json_output_never_raises(obj: object) -> None:
    result = parse_json_output(obj)  # type: ignore[arg-type]
    assert isinstance(result, list)


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=0, max_size=500))
@settings(max_examples=200)
def test_parse_session_line_handles_arbitrary_unicode_text(text: str) -> None:
    data = text.encode("utf-8", errors="ignore")
    result = parse_session_line(data)
    assert result is None or result.model_dump() is not None


def test_parse_session_line_handles_embedded_nul_and_huge_line() -> None:
    assert parse_session_line(b"\x00\x00\x00") is None
    huge = b'{"tool": "write", "paths": ["' + b"a" * (3 * 1024 * 1024) + b'"]}'
    # Should not raise, regardless of outcome.
    parse_session_line(huge)
