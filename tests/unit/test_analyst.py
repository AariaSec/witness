"""Analyst: offline deterministic template path (the only path in G1)."""

from __future__ import annotations

from pathlib import Path

from witness.analyst.run import analyze
from witness.analyst.tools import get_record, query
from witness.bundle import build_bundle
from witness.ledger import Ledger
from witness.models import Finding, FindingKind, Manifest, MarkerRead, Severity


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


def test_analyze_offline_no_findings(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ledger = Ledger(run_dir / "ledger.jsonl")
    ledger.append(_manifest())
    ledger.close()
    bundle_path = run_dir / "bundle.jsonl"
    build_bundle(run_dir, bundle_path)

    report = analyze(bundle_path, client=None)
    assert report.analyst_status == "offline"
    assert report.tool_calls == 0
    assert report.summary_codes == ["NO_FINDINGS"]
    assert report.confidence == 1.0
    assert all(len(code) <= 64 for code in report.summary_codes)


def test_analyze_offline_with_findings(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ledger = Ledger(run_dir / "ledger.jsonl")
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.append(
        Finding(
            fkind=FindingKind.marker_read,
            severity=Severity.warn,
            evidence_seqs=[1],
            detector_version="1.0",
        )
    )
    ledger.close()
    bundle_path = run_dir / "bundle.jsonl"
    build_bundle(run_dir, bundle_path)

    report = analyze(bundle_path, client=None)
    assert report.analyst_status == "offline"
    assert "DECOY_KEY_READ" in report.summary_codes
    assert len(report.timeline) == 1
    assert report.timeline[0].seq_refs == [1]


def test_analyst_tools_get_record_and_query() -> None:
    records = [
        {"seq": 0, "kind": "manifest", "run_id": "r1"},
        {"seq": 1, "kind": "marker_read", "peer_pid": 1},
        {"seq": 2, "kind": "marker_read", "peer_pid": 2},
    ]
    assert get_record(records, 1)["peer_pid"] == 1
    matched = query(records, "marker_read")
    assert len(matched) == 2
    filtered = query(records, "marker_read", {"peer_pid": 2})
    assert len(filtered) == 1
    assert filtered[0]["seq"] == 2


def test_analyst_tools_get_record_missing_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_record([{"seq": 0, "kind": "manifest"}], 99)
