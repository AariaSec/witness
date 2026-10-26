"""Read-only tools an LLM analyst would call over an already-bundled,
already-content-free record set. Both operate on plain dicts (the JSON
form of bundle records) so a real tool-calling LLMClient can pass JSON
straight through without importing pydantic models."""

from __future__ import annotations

from typing import Any


def get_record(records: list[dict[str, Any]], seq: int) -> dict[str, Any]:
    """Return the record with the given `seq`. Raises `KeyError` if absent."""
    for rec in records:
        if rec.get("seq") == seq:
            return rec
    raise KeyError(seq)


def query(
    records: list[dict[str, Any]],
    kind: str,
    filt: dict[str, str | int | bool] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return up to `limit` records matching `kind` and every key/value in
    `filt`."""
    filt = filt or {}
    results: list[dict[str, Any]] = []
    for rec in records:
        if rec.get("kind") != kind:
            continue
        if all(rec.get(k) == v for k, v in filt.items()):
            results.append(rec)
        if len(results) >= limit:
            break
    return results


__all__ = ["get_record", "query"]
