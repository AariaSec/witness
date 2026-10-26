"""Integration: `witness record` over the scripted `sim_agent`, end to end.

Mirrors the architecture doc's `test_record_sim_agent.py` spec (§4.2):

  exfil   -> marker_read, outbound_post(contains_marker=True),
             finding(outbound_post, stop), action_result(stop_pgroup, ok=True),
             receipt; verify_chain true; `witness bundle` exits 0; bundle
             passes leakscan.
  benign  -> zero findings of severity `stop`.
  escape  -> the sim agent spawns a grandchild in a new session; the run
             still completes cleanly with a signed receipt (the dedicated
             `pgroup_escape` *detector* is out of scope for G1 — see
             CLAUDE/notes — but the action-level extra_pids fallback is
             wired, see `ActionRunner.note_extra_pid`).

Time budget: well under the architecture doc's 90s for all three.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from witness.bundle import build_bundle
from witness.cli import _run_record
from witness.config import RecordConfig
from witness.leakscan import load_allowed_keys, scan_record
from witness.ledger import read_ledger, verify_chain
from witness.models import FindingKind, Kind, Severity


def _record(tmp_path: Path, scenario: str, max_seconds: float = 20.0) -> Path:
    lab = tmp_path / "lab"
    runs_dir = tmp_path / "runs"
    cfg = RecordConfig(lab=lab, max_seconds=max_seconds)
    cmd = [sys.executable, "-m", "witness.demo.sim_agent", "--scenario", scenario]
    return _run_record(cfg, cmd, runs_dir)


def test_exfil_scenario_end_to_end(tmp_path: Path) -> None:
    run_dir = _record(tmp_path, "exfil")
    records = read_ledger(run_dir / "ledger.jsonl")

    ok, bad = verify_chain(records)
    assert ok, f"chain broken at seq={bad}"

    kinds = [r.kind for r in records]
    assert Kind.marker_read in kinds
    assert Kind.outbound_post in kinds
    assert Kind.receipt in kinds

    outbound = next(r for r in records if r.kind == Kind.outbound_post)
    assert outbound.contains_marker is True  # type: ignore[attr-defined]

    findings = [r for r in records if r.kind == Kind.finding]
    assert any(
        f.fkind == FindingKind.outbound_post and f.severity == Severity.stop  # type: ignore[attr-defined]
        for f in findings
    )

    action_results = [r for r in records if r.kind == Kind.action_result]
    stop_results = [r for r in action_results if r.action == "stop_pgroup"]  # type: ignore[attr-defined]
    assert any(r.ok for r in stop_results), "stop_pgroup should have succeeded"

    out = run_dir / "bundle.jsonl"
    info = build_bundle(run_dir, out)
    assert out.exists()
    assert info.receipt_ok is True

    allowed = load_allowed_keys()
    for rec in records:
        assert scan_record(rec.model_dump(mode="json"), allowed) == []


def test_benign_scenario_has_zero_stop_findings(tmp_path: Path) -> None:
    run_dir = _record(tmp_path, "benign")
    records = read_ledger(run_dir / "ledger.jsonl")
    ok, bad = verify_chain(records)
    assert ok, f"chain broken at seq={bad}"

    findings = [r for r in records if r.kind == Kind.finding]
    stop_findings = [f for f in findings if f.severity == Severity.stop]  # type: ignore[attr-defined]
    assert stop_findings == []

    out = run_dir / "bundle.jsonl"
    build_bundle(run_dir, out)
    assert out.exists()


def test_escape_scenario_completes_with_signed_receipt(tmp_path: Path) -> None:
    run_dir = _record(tmp_path, "escape")
    records = read_ledger(run_dir / "ledger.jsonl")
    ok, bad = verify_chain(records)
    assert ok, f"chain broken at seq={bad}"
    assert records[-1].kind == Kind.receipt

    out = run_dir / "bundle.jsonl"
    info = build_bundle(run_dir, out)
    assert info.receipt_ok is True


def test_write_scenario_fires_protected_write(tmp_path: Path) -> None:
    run_dir = _record(tmp_path, "write")
    records = read_ledger(run_dir / "ledger.jsonl")
    ok, bad = verify_chain(records)
    assert ok, f"chain broken at seq={bad}"

    findings = [r for r in records if r.kind == Kind.finding]
    assert any(f.fkind == FindingKind.protected_write for f in findings)  # type: ignore[attr-defined]

    out = run_dir / "bundle.jsonl"
    info = build_bundle(run_dir, out)
    assert info.findings.get("protected_write") == 1


def test_cli_bundle_command_exits_0(tmp_path: Path) -> None:
    run_dir = _record(tmp_path, "mismatch")
    result = subprocess.run(
        [sys.executable, "-m", "witness.cli", "bundle", str(run_dir)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
