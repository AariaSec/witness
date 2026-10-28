"""`witness.watch.line_for`: one record -> one line of rich markup.
Content-free discipline applies here too -- asserts every produced line
is built only from existing model fields (seq/ts_mono/enum values/paths),
never a fabricated string, and that severity maps to the right style tag."""

from __future__ import annotations

from witness.models import (
    ActionResult,
    Finding,
    FindingKind,
    FsEvent,
    FsOp,
    Manifest,
    MarkerRead,
    Receipt,
    ReceiptBody,
    Severity,
)
from witness.watch import line_for


def _finding(severity: Severity, fkind: FindingKind = FindingKind.marker_read) -> Finding:
    return Finding(
        seq=5,
        kind="finding",
        fkind=fkind,
        severity=severity,
        evidence_seqs=[1, 2],
        detector_version="1.0",
    )


def test_stop_finding_renders_bold_red() -> None:
    line = line_for(_finding(Severity.stop, FindingKind.credential_persist))
    assert "[bold red]" in line
    assert "STOP" in line
    assert "credential_persist" in line
    assert "#5" in line


def test_warn_finding_renders_bold_yellow() -> None:
    line = line_for(_finding(Severity.warn))
    assert "[bold yellow]" in line
    assert "WARN" in line


def test_info_finding_renders_bold_blue() -> None:
    line = line_for(_finding(Severity.info))
    assert "[bold blue]" in line
    assert "INFO" in line


def test_fs_event_with_contains_marker_is_flagged_red() -> None:
    rec = FsEvent(
        seq=3,
        kind="fs_event",
        op=FsOp.create,
        path="cache/credentials.json",
        bytes=12,
        sha256=None,
        protected=False,
        contains_marker=True,
    )
    line = line_for(rec)
    assert "contains_marker" in line
    assert "[bold red]" in line
    assert "cache/credentials.json" in line


def test_fs_event_without_contains_marker_is_not_flagged() -> None:
    rec = FsEvent(
        seq=3,
        kind="fs_event",
        op=FsOp.create,
        path="notes.txt",
        bytes=5,
        sha256=None,
        protected=False,
        contains_marker=False,
    )
    line = line_for(rec)
    assert "[bold red]" not in line


def test_manifest_simulated_flag_is_shown() -> None:
    rec = Manifest(
        seq=0,
        kind="manifest",
        bundle_schema="1.0",
        witness_version="0.1.0",
        run_id="20261028-000000-aaaa",
        platform="darwin",
        marker_port=47101,
        sink_port=47102,
        lab_root_digest="a" * 64,
        protected_paths=[],
        policy_hash="b" * 64,
        assistant_argv_digest="c" * 64,
        simulated=True,
        pubkey="pk",
    )
    line = line_for(rec)
    assert "(simulated)" in line
    assert "20261028-000000-aaaa" in line


def test_marker_read_escaped_peer_is_flagged() -> None:
    rec = MarkerRead(seq=1, kind="marker_read", peer_pid=123, peer_exe=None, path="/v1/token", ua_digest=None, peer_escaped=True)
    line = line_for(rec)
    assert "escaped peer" in line


def test_receipt_shows_stop_status_and_key_prefix() -> None:
    rec = Receipt(
        seq=10,
        kind="receipt",
        body=ReceiptBody(
            run_id="r1",
            final_digest="d" * 64,
            records=10,
            findings={},
            stop_status="ok",
            policy_hash="e" * 64,
            signed_at=0.0,
            pubkey="abcdefghijklmnop",
        ),
        sig="sig",
    )
    line = line_for(rec)
    assert "receipt signed" in line
    assert "stop=ok" in line
    assert "abcdefghij" in line  # first 10 chars of pubkey


def test_action_result_failure_is_flagged() -> None:
    rec = ActionResult(seq=6, kind="action_result", action="stop_pgroup", finding_seq=5, ok=False, latency_ms=12, detail="failed")
    line = line_for(rec)
    assert "FAILED" in line
    assert "[bold red]" in line
