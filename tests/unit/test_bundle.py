"""Bundle: happy path + chain re-verification.

The allowed-keys whitelist / secret-pattern refusal path is exercised in
`tests/unit/test_leakscan.py` instead of here: by the time a record
reaches `build_bundle`, it has already round-tripped through
`read_ledger`'s pydantic parse, which (via `extra="forbid"` on every
model) already refuses an unknown top-level key *before* the whitelist
ever runs. The whitelist is a second, independent line of defense for
anything read as plain JSON without going through those models at all —
exactly what `scripts/leakscan.py` does, and what `test_leakscan.py`
covers directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from witness.bundle import BundleChainInvalid, build_bundle, receipt_of, validate_bundle
from witness.ledger import Ledger, read_ledger
from witness.models import Manifest, MarkerRead

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_MUSE_BUNDLE = (
    _REPO_ROOT
    / "runs"
    / "frozen"
    / "muse-real-agent-proof-20261026-185538-7c88"
    / "bundle.jsonl"
)
_BENIGN_CORPUS_BUNDLE = _REPO_ROOT / "corpus" / "benign" / "b01.jsonl"


def _manifest() -> Manifest:
    return Manifest(
        bundle_schema="1.0",
        witness_version="0.1.0",
        run_id="r1",
        platform="darwin",
        marker_port=1,
        sink_port=2,
        lab_root_digest="0" * 64,
        protected_paths=["protected"],
        policy_hash="0" * 64,
        assistant_argv_digest="0" * 64,
        simulated=True,
        pubkey="abc",
    )


def _make_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ledger = Ledger(run_dir / "ledger.jsonl")
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.close()
    return run_dir


def test_build_bundle_happy_path(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    out = run_dir / "bundle.jsonl"
    info = build_bundle(run_dir, out)
    assert out.exists()
    assert info.records == 2
    assert info.run_id == "r1"

    info2 = validate_bundle(out)
    assert info2.records == 2


def test_build_bundle_refuses_disallowed_key_is_caught_by_pydantic_first(tmp_path: Path) -> None:
    """A record with an unknown top-level key never even reaches the
    whitelist: `read_ledger`'s pydantic parse (`extra="forbid"`) refuses it
    first. This is the primary defense; see `test_leakscan.py` for the
    independent whitelist check on plain (non-pydantic) JSON."""
    run_dir = _make_run(tmp_path)
    ledger_path = run_dir / "ledger.jsonl"
    lines = ledger_path.read_text().splitlines()
    obj = json.loads(lines[0])
    obj["this_is_not_whitelisted"] = "leaked prose would go here"
    lines[0] = json.dumps(obj)
    ledger_path.write_text("\n".join(lines) + "\n")

    out = run_dir / "bundle.jsonl"
    with pytest.raises(ValidationError):
        build_bundle(run_dir, out)
    assert not out.exists()


def test_build_bundle_refuses_broken_chain(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    ledger_path = run_dir / "ledger.jsonl"
    lines = ledger_path.read_text().splitlines()
    obj = json.loads(lines[1])
    obj["peer_pid"] = 999999
    lines[1] = json.dumps(obj)
    ledger_path.write_text("\n".join(lines) + "\n")

    out = run_dir / "bundle.jsonl"
    with pytest.raises(BundleChainInvalid):
        build_bundle(run_dir, out)
    assert not out.exists()


def test_validate_bundle_round_trips_on_unmodified_output(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    out = run_dir / "bundle.jsonl"
    build_bundle(run_dir, out)
    info = validate_bundle(out)
    assert info.records == 2


def test_validate_bundle_new_fields_default_to_sane_values(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path)
    out = run_dir / "bundle.jsonl"
    build_bundle(run_dir, out)
    info = validate_bundle(out)
    # This fixture has no receipt at all (see `_make_run`) — `receipt_ok`
    # and the new `receipt_status`/`stop_findings` fields must say so
    # clearly, never silently.
    assert info.receipt_ok is False
    assert info.receipt_status == "missing"
    assert info.stop_findings == 0


# --- Real, committed bundles as fixtures (not only synthetic) ---------


def test_real_muse_bundle_still_validates_cleanly() -> None:
    info = validate_bundle(_REAL_MUSE_BUNDLE)
    assert info.receipt_ok is True
    assert info.receipt_status == "ok"
    assert info.records == 13
    assert info.stop_findings == 0  # marker_read only, severity=warn


def test_real_muse_bundle_receipt_has_no_v02_fields_set() -> None:
    """This bundle predates Receipt v0.2 — it must round-trip with the
    new fields at their defaults, not with any garbage/guessed value."""
    records = read_ledger(_REAL_MUSE_BUNDLE)
    receipt = receipt_of(records)
    assert receipt is not None
    assert receipt.body.git_commit_sha is None
    assert receipt.body.git_tree_digest is None
    assert receipt.body.changed_file_digests == {}
    assert receipt.body.coverage == []


def test_real_benign_corpus_bundle_still_validates_cleanly() -> None:
    info = validate_bundle(_BENIGN_CORPUS_BUNDLE)
    assert info.receipt_ok is True
    assert info.receipt_status == "ok"
    assert info.findings == {}
    assert info.stop_findings == 0
