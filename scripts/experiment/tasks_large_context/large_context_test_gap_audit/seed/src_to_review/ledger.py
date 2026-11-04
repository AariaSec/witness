"""Append-only, hash-chained ledger.

`Ledger.append` is the *only* place `seq`, `ts_wall`, `ts_mono`, `prev`,
and `digest` are assigned. Records are frozen pydantic models, so
"assigning" means producing a new, re-validated instance — the caller's
original (placeholder) instance is never mutated.

digest = sha256( prev_digest_bytes || canonical_json(record_without_digest) )

where `prev_digest_bytes` is the UTF-8 encoding of the previous record's
hex digest, or `b""` for the first record (seq 0).
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from witness.canon import canonical_json, sha256_hex
from witness.models import (
    Record,
    strip_additive_record_field_defaults,
    strip_receipt_body_v02_defaults,
)

_RecordAdapter: TypeAdapter[Record] = TypeAdapter(Record)


def _strip_default_v02_fields(payload: dict[str, object]) -> None:
    """Strip every additive-field-at-default case this codebase has
    accumulated: top-level (any record kind, via
    `strip_additive_record_field_defaults`) and nested (`payload["body"]`,
    receipt-only, via `strip_receipt_body_v02_defaults`) — a no-op for a
    record/field combination that was never touched. See both functions'
    docstrings in `models.py` for why this must run before hashing any
    record for the chain digest."""
    strip_additive_record_field_defaults(payload)
    body = payload.get("body")
    if isinstance(body, dict):
        strip_receipt_body_v02_defaults(body)


def _record_digest(rec: BaseModel, prev: str | None) -> str:
    payload = rec.model_dump(mode="json")
    payload.pop("digest", None)
    _strip_default_v02_fields(payload)
    prev_bytes = prev.encode("utf-8") if prev else b""
    return sha256_hex(prev_bytes + canonical_json(payload))


class Ledger:
    """Single-writer, append-only, hash-chained JSONL ledger."""

    def __init__(self, path: Path, fsync: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fsync = fsync
        self._lock = threading.Lock()
        self._next_seq = 0
        self._prev_digest: str | None = None
        self._start_mono = time.monotonic()
        self._callbacks: list[Callable[[BaseModel], None]] = []
        self._fh = open(self.path, "a", encoding="utf-8")

    def on_append(self, cb: Callable[[BaseModel], None]) -> None:
        self._callbacks.append(cb)

    def append(self, rec: BaseModel) -> BaseModel:
        """Assign seq/ts_wall/ts_mono/prev/digest to `rec`, append it to
        the ledger file, and return the new frozen+validated record."""
        with self._lock:
            seq = self._next_seq
            prev = self._prev_digest
            ts_wall = time.time()
            ts_mono = time.monotonic() - self._start_mono

            draft = rec.model_copy(
                update={
                    "seq": seq,
                    "ts_wall": ts_wall,
                    "ts_mono": ts_mono,
                    "prev": prev,
                    "digest": None,
                }
            )
            digest = _record_digest(draft, prev)

            final_payload = draft.model_dump(mode="json")
            final_payload["digest"] = digest
            # Re-validate through the discriminated union so an invalid
            # field (e.g. a malformed digest pattern) can never reach disk.
            final = _RecordAdapter.validate_python(final_payload)

            self._fh.write(canonical_json(final_payload).decode("utf-8"))
            self._fh.write("\n")
            if self._fsync:
                self._fh.flush()
                os.fsync(self._fh.fileno())

            self._next_seq = seq + 1
            self._prev_digest = digest

        for cb in self._callbacks:
            cb(final)
        return final

    def close(self) -> str | None:
        with self._lock:
            self._fh.flush()
            if self._fsync:
                with contextlib.suppress(OSError):
                    os.fsync(self._fh.fileno())
            self._fh.close()
            return self._prev_digest

    @property
    def record_count(self) -> int:
        return self._next_seq

    @property
    def final_digest(self) -> str | None:
        return self._prev_digest


def read_ledger(path: Path) -> list[Record]:
    """Read and validate every record in a ledger file, in order."""
    records: list[Record] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(_RecordAdapter.validate_json(line))
    return records


def verify_chain(records: Sequence[BaseModel]) -> tuple[bool, int | None]:
    """Recompute the hash chain over `records` and compare against the
    stored `prev`/`digest` fields.

    Returns `(True, None)` if the chain is intact, else
    `(False, first_bad_seq)`.
    """
    prev: str | None = None
    for i, rec in enumerate(records):
        seq = getattr(rec, "seq", i)
        stored_prev = getattr(rec, "prev", None)
        stored_digest = getattr(rec, "digest", None)
        if stored_prev != prev:
            return False, seq
        expected_digest = _record_digest(rec, prev)
        if stored_digest != expected_digest:
            return False, seq
        prev = stored_digest
    return True, None


__all__ = ["Ledger", "read_ledger", "verify_chain"]
