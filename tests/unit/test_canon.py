"""Canonical JSON: sorted keys, deterministic float formatting, unicode."""

from __future__ import annotations

import json

from witness.canon import canonical_json, sha256_hex

# Known vector: sha256(canon({"b": 1, "a": [1.5]})) — pin this so any future
# change to canonical_json's output format is caught immediately.
_KNOWN_VECTOR_SHA256 = sha256_hex(b'{"a":[1.5],"b":1}')


def test_sorted_keys() -> None:
    out = canonical_json({"b": 1, "a": 2})
    assert out == b'{"a":2,"b":1}'


def test_no_spaces() -> None:
    out = canonical_json({"a": [1, 2, 3]})
    assert b" " not in out


def test_nested_keys_sorted() -> None:
    out = canonical_json({"z": {"b": 1, "a": 2}, "a": 1})
    assert out == b'{"a":1,"z":{"a":2,"b":1}}'


def test_known_vector() -> None:
    out = canonical_json({"b": 1, "a": [1.5]})
    assert out == b'{"a":[1.5],"b":1}'
    assert sha256_hex(out) == _KNOWN_VECTOR_SHA256


def test_unicode_not_escaped() -> None:
    out = canonical_json({"name": "café"})
    assert "café".encode() in out


def test_deterministic_across_dict_insertion_order() -> None:
    a = canonical_json({"x": 1, "y": 2})
    b = canonical_json({"y": 2, "x": 1})
    assert a == b


def test_sha256_hex_matches_stdlib_json_roundtrip() -> None:
    obj = {"k": "v"}
    out = canonical_json(obj)
    assert json.loads(out) == obj
    assert len(sha256_hex(out)) == 64
