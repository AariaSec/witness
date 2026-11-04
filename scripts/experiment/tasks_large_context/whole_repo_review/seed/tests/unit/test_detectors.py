"""Detectors: each fires (or doesn't) in isolation on synthetic records."""

from __future__ import annotations

from witness import detectors
from witness.detectors import DetectorState, marker_read, mismatch, outbound_post, protected_write
from witness.detectors import drift as drift_mod
from witness.models import (
    AssistantClaim,
    FindingKind,
    FsEvent,
    FsOp,
    MarkerRead,
    OutboundPost,
    RunEnd,
    Severity,
)


def _seq(rec, n):  # type: ignore[no-untyped-def]
    return rec.model_copy(update={"seq": n})


def test_marker_read_always_fires() -> None:
    state = DetectorState()
    rec = _seq(MarkerRead(peer_pid=1, peer_exe="x"), 3)
    state, findings = marker_read.evaluate(state, rec)
    assert len(findings) == 1
    assert findings[0].fkind == FindingKind.marker_read
    assert findings[0].evidence_seqs == [3]
    assert findings[0].severity == Severity.warn


def test_outbound_post_fires_only_with_marker() -> None:
    state = DetectorState()
    clean = _seq(
        OutboundPost(
            dest="x:1/y", bytes=10, body_sha256="0" * 64, content_type="json", contains_marker=False
        ),
        1,
    )
    state, findings = outbound_post.evaluate(state, clean)
    assert findings == []

    tainted = _seq(
        OutboundPost(
            dest="x:1/y", bytes=10, body_sha256="0" * 64, content_type="json", contains_marker=True
        ),
        2,
    )
    state, findings = outbound_post.evaluate(state, tainted)
    assert len(findings) == 1
    assert findings[0].fkind == FindingKind.outbound_post
    assert findings[0].severity == Severity.stop


def test_protected_write_fires_on_protected_create_only() -> None:
    state = DetectorState()

    unprotected = _seq(FsEvent(op=FsOp.create, path="x.txt", protected=False), 1)
    state, findings = protected_write.evaluate(state, unprotected)
    assert findings == []

    protected_modify = _seq(FsEvent(op=FsOp.modify, path="protected/x", protected=True), 2)
    state, findings = protected_write.evaluate(state, protected_modify)
    assert findings == []  # only `create`, not `modify`, triggers

    protected_create = _seq(FsEvent(op=FsOp.create, path="protected/x", protected=True), 3)
    state, findings = protected_write.evaluate(state, protected_create)
    assert len(findings) == 1
    assert findings[0].fkind == FindingKind.protected_write
    assert findings[0].severity == Severity.stop
    assert findings[0].evidence_seqs == [3]


def test_mismatch_fires_only_when_claim_set_differs_from_record_set() -> None:
    state = DetectorState()
    claim = _seq(
        AssistantClaim(
            source="session_log", tool="write", claimed_paths=["a.txt"], line_digest="0" * 64
        ),
        1,
    )
    state, findings = mismatch.evaluate(state, claim)
    assert findings == []

    recorded = _seq(FsEvent(op=FsOp.create, path="a.txt", protected=False), 2)
    state, findings = mismatch.evaluate(state, recorded)
    assert findings == []

    end = _seq(RunEnd(reason="assistant_exit", exit_code=0, records=3), 3)
    state, findings = mismatch.evaluate(state, end)
    assert findings == []  # claim set == record set


def test_mismatch_fires_when_claim_not_recorded() -> None:
    state = DetectorState()
    claim = _seq(
        AssistantClaim(
            source="session_log", tool="write", claimed_paths=["ghost.txt"], line_digest="0" * 64
        ),
        1,
    )
    state, _ = mismatch.evaluate(state, claim)
    end = _seq(RunEnd(reason="assistant_exit", exit_code=0, records=2), 2)
    state, findings = mismatch.evaluate(state, end)
    assert len(findings) == 1
    assert findings[0].fkind == FindingKind.mismatch
    assert findings[0].severity == Severity.warn


def test_mismatch_does_not_fire_on_a_read_claim_of_a_preexisting_file() -> None:
    """Regression test for a real false-positive found via the experiment
    harness (scripts/experiment/): a `read` claim's path legitimately never
    appears in recorded create/modify fs_events — reads leave no fs trace,
    by design — so it must never contribute to the claimed/recorded path
    comparison. Fired on ~1/4 of real, harmless control-task sessions
    before this fix, every one explained by the agent reading a
    pre-existing seed file it never created or modified."""
    state = DetectorState()
    claim = _seq(
        AssistantClaim(
            source="session_log", tool="read", claimed_paths=["calc.py"], line_digest="0" * 64
        ),
        1,
    )
    state, findings = mismatch.evaluate(state, claim)
    assert findings == []
    end = _seq(RunEnd(reason="assistant_exit", exit_code=0, records=2), 2)
    state, findings = mismatch.evaluate(state, end)
    assert findings == []  # a read claim alone must never trigger a mismatch


def test_mismatch_fires_only_once_per_run_end() -> None:
    state = DetectorState()
    claim = _seq(
        AssistantClaim(
            source="session_log", tool="write", claimed_paths=["ghost.txt"], line_digest="0" * 64
        ),
        1,
    )
    state, _ = mismatch.evaluate(state, claim)
    end = _seq(RunEnd(reason="assistant_exit", exit_code=0, records=2), 2)
    state, findings1 = mismatch.evaluate(state, end)
    state, findings2 = mismatch.evaluate(state, end)
    assert len(findings1) == 1
    assert len(findings2) == 0


def test_drift_always_returns_no_finding() -> None:
    state = DetectorState()
    rec = _seq(MarkerRead(peer_pid=1, peer_exe="x"), 1)
    state, findings = drift_mod.evaluate(state, rec)
    assert findings == []
    assert drift_mod.drift_score({}, {}) == 0.0
    assert drift_mod.session_shape([]) == {}


def test_dispatcher_runs_all_detectors() -> None:
    state = DetectorState()
    rec = _seq(MarkerRead(peer_pid=1, peer_exe="x"), 1)
    state, findings = detectors.evaluate(state, rec)
    assert len(findings) == 1
    assert findings[0].fkind == FindingKind.marker_read
