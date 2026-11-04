"""Canonical JSON encoding + sha256 helpers.

Canonical form: sorted keys (recursively), no insignificant whitespace,
UTF-8, floats rendered via Python's own `repr()` semantics (which is what
the stdlib `json` encoder already uses for floats). Determinism here is
what makes the hash-chained ledger meaningful — two parties (recorder,
re-verifier, console) must compute byte-identical digests from the same
logical record regardless of how it happened to be stored on disk.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def _to_jsonable(obj: Any) -> Any:
    """Convert a pydantic model (or plain dict/list/scalar) into something
    `json.dumps` can serialize deterministically."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return obj


def canonical_json(obj: BaseModel | dict[str, Any] | list[Any]) -> bytes:
    """Serialize `obj` to canonical JSON bytes: sorted keys, no spaces,
    UTF-8, deterministic float formatting."""
    data = _to_jsonable(obj)
    text = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex sha256 digest of `data`."""
    return hashlib.sha256(data).hexdigest()


__all__ = ["canonical_json", "sha256_hex"]
