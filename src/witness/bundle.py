"""Ledger → `bundle.jsonl` export.

Validates every record against the `allowed_keys.yaml` whitelist
(defense-in-depth on top of pydantic's `extra="forbid"`), re-verifies the
hash chain, and emits a single `bundle.jsonl` — the only artifact the
console or analyst ever sees. On any whitelist/secret-pattern violation,
refuses to emit, writes a `QUARANTINED` marker next to the ledger, and
raises `BundleQuarantined` (the CLI maps this to exit code 3).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from witness.actions.receipt import verify_receipt
from witness.canon import canonical_json
from witness.leakscan import load_allowed_keys, scan_record
from witness.ledger import read_ledger, verify_chain
from witness.models import Finding, Kind, Receipt, Record, Report


class BundleQuarantined(Exception):
    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__(f"{len(violations)} leak-scan violation(s)")


class BundleChainInvalid(Exception):
    def __init__(self, first_bad_seq: int | None) -> None:
        self.first_bad_seq = first_bad_seq
        super().__init__(f"chain invalid at seq={first_bad_seq}")


class BundleInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    records: int
    schema_version: str
    findings: dict[str, int]
    receipt_ok: bool


def _check_records(records: list[Record]) -> None:
    allowed_keys = load_allowed_keys()
    violations: list[str] = []
    for rec in records:
        payload = rec.model_dump(mode="json")
        violations.extend(scan_record(payload, allowed_keys))
    if violations:
        raise BundleQuarantined(violations)


def _finding_counts(records: list[Record]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rec in records:
        if rec.kind == Kind.finding:
            assert isinstance(rec, Finding)
            counts[rec.fkind.value] = counts.get(rec.fkind.value, 0) + 1
    return counts


def _receipt_ok(records: list[Record]) -> bool:
    for rec in records:
        if rec.kind == Kind.receipt:
            assert isinstance(rec, Receipt)
            return verify_receipt(rec)
    return False


def _run_id_of(records: list[Record]) -> str:
    for rec in records:
        if rec.kind == Kind.manifest:
            return rec.run_id
    return "unknown"


def _schema_of(records: list[Record]) -> str:
    for rec in records:
        if rec.kind == Kind.manifest:
            return rec.bundle_schema
    return "unknown"


def _append_report(records: list[Record], report: Report) -> list[Record]:
    """Append `report` to `records`, assigning seq/prev/digest exactly as
    the ledger writer would (so the chain stays verifiable end-to-end)."""
    from witness.ledger import _record_digest  # local import: internal helper reuse

    prev = records[-1].digest if records else None
    seq = records[-1].seq + 1 if records else 0
    draft = report.model_copy(update={"seq": seq, "prev": prev, "digest": None})
    digest = _record_digest(draft, prev)
    final = draft.model_copy(update={"digest": digest})
    return [*records, final]


def build_bundle(run_dir: Path, out: Path, report: Report | None = None) -> BundleInfo:
    run_dir = Path(run_dir)
    ledger_path = run_dir / "ledger.jsonl"
    records = read_ledger(ledger_path)

    if report is not None:
        records = _append_report(records, report)

    ok, bad_seq = verify_chain(records)
    if not ok:
        raise BundleChainInvalid(bad_seq)

    try:
        _check_records(records)
    except BundleQuarantined:
        marker = run_dir / "QUARANTINED"
        marker.write_text("bundle refused: leak-scan violation(s) found\n", encoding="utf-8")
        raise

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(canonical_json(rec.model_dump(mode="json")).decode("utf-8"))
            fh.write("\n")

    return BundleInfo(
        run_id=_run_id_of(records),
        records=len(records),
        schema_version=_schema_of(records),
        findings=_finding_counts(records),
        receipt_ok=_receipt_ok(records),
    )


def validate_bundle(path: Path) -> BundleInfo:
    """Re-validate an already-built `bundle.jsonl`: schema parse, whitelist,
    chain, receipt."""
    from witness.ledger import read_ledger as _read  # same JSONL reader works

    records = _read(Path(path))
    ok, bad_seq = verify_chain(records)
    if not ok:
        raise BundleChainInvalid(bad_seq)
    _check_records(records)
    return BundleInfo(
        run_id=_run_id_of(records),
        records=len(records),
        schema_version=_schema_of(records),
        findings=_finding_counts(records),
        receipt_ok=_receipt_ok(records),
    )


__all__ = [
    "BundleChainInvalid",
    "BundleInfo",
    "BundleQuarantined",
    "build_bundle",
    "validate_bundle",
]
