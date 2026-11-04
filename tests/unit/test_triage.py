"""Triage: a model proposes, a deterministic verifier must corroborate.

The model is faked here; what is under test is that a wrong or
uncorroborated verdict can never retract a finding.
"""

from __future__ import annotations

from pathlib import Path

from witness.analyst.client import LLMClientError
from witness.analyst.triage import _corroborate, triage
from witness.models import AssistantClaim, ClaimTool, Finding, FindingKind, FsEvent, FsOp, Severity

_REPO = Path(__file__).resolve().parents[2]
# real frozen Muse Code bundle whose seq-20 `mismatch` finding came from the
# since-fixed read-vs-write bug: every claim behind it is a read/search.
_BUNDLE = _REPO / "runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl"


class _Fake:
    _model = "fake-meta-model"

    def __init__(self, payload: dict | Exception) -> None:
        self.payload = payload

    def complete(self, system, messages, tools, schema):  # type: ignore[no-untyped-def]
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _v(verdict: str, reason: str, cited: list[int]) -> dict:
    return {"verdicts": [{"finding_seq": 20, "verdict": verdict, "reason": reason, "cited_seqs": cited}],
            "confidence": 0.9}


def test_offline_adjudicates_nothing() -> None:
    rep = triage(_BUNDLE, client=None)
    assert rep.status == "offline" and rep.items[0].label == "NOT_ADJUDICATED"


def test_corroborated_retraction_on_real_bundle() -> None:
    rep = triage(_BUNDLE, client=_Fake(_v("unsupported", "CLAIM_WAS_READ_NOT_WRITE", [9, 10, 17])))
    assert rep.status == "ok" and rep.model_id == "fake-meta-model"
    assert rep.items[0].label == "RETRACTED" and rep.items[0].corroborated


def test_uncorroborated_confirmation_is_overruled() -> None:
    # model claims a real discrepancy; the record shows every write is recorded
    rep = triage(_BUNDLE, client=_Fake(_v("supported", "WRITE_CLAIM_UNRECORDED", [10])))
    assert rep.items[0].label == "NEEDS_HUMAN" and not rep.items[0].corroborated


def test_citing_outside_the_evidence_never_retracts() -> None:
    rep = triage(_BUNDLE, client=_Fake(_v("unsupported", "CLAIM_WAS_READ_NOT_WRITE", [9, 10, 999])))
    assert rep.items[0].label == "NEEDS_HUMAN"


def test_client_failure_falls_back_offline() -> None:
    rep = triage(_BUNDLE, client=_Fake(LLMClientError("boom")))
    assert rep.status == "offline" and rep.items[0].label == "NOT_ADJUDICATED"


def test_malformed_shape_falls_back_offline() -> None:
    assert triage(_BUNDLE, client=_Fake({"nope": 1})).status == "offline"


def _claim(seq: int, tool: ClaimTool, paths: list[str]) -> AssistantClaim:
    return AssistantClaim(seq=seq, ts_wall=0.0, ts_mono=0.0, source="session_log", tool=tool,
                          claimed_paths=paths, claimed_hosts=[], line_digest="0" * 64)


def _fs(seq: int, path: str) -> FsEvent:
    return FsEvent(seq=seq, ts_wall=0.0, ts_mono=0.0, op=FsOp.create, path=path, protected=False)


def _finding(seqs: list[int]) -> Finding:
    return Finding(seq=99, ts_wall=0.0, ts_mono=0.0, fkind=FindingKind.mismatch,
                   severity=Severity.warn, evidence_seqs=seqs, detector_version="1.0")


def test_real_unrecorded_write_claim_is_not_retractable() -> None:
    recs = {1: _claim(1, ClaimTool.write, ["out/report.txt"]), 2: _fs(2, "other.txt")}
    f = _finding([1, 2])
    ok, _ = _corroborate("unsupported", "CLAIM_WAS_READ_NOT_WRITE", [1], f, recs)
    assert not ok
    ok, _ = _corroborate("supported", "WRITE_CLAIM_UNRECORDED", [1], f, recs)
    assert ok


def test_path_alias_corroborated_by_same_file_name() -> None:
    recs = {1: _claim(1, ClaimTool.write, ["report.txt"]), 2: _fs(2, "out/report.txt")}
    f = _finding([1, 2])
    assert _corroborate("unsupported", "PATH_ALIAS_SAME_FILE", [1, 2], f, recs)[0]
    # same claim, but the cited recorded path is a different file -> no
    recs[2] = _fs(2, "out/other.txt")
    assert not _corroborate("unsupported", "PATH_ALIAS_SAME_FILE", [1, 2], f, recs)[0]


def test_same_file_name_in_different_directory_is_not_an_alias() -> None:
    recs = {1: _claim(1, ClaimTool.write, ["a/x.env"]), 2: _fs(2, "b/x.env")}
    f = _finding([1, 2])
    assert not _corroborate("unsupported", "PATH_ALIAS_SAME_FILE", [1, 2], f, recs)[0]
    # ...and the opposite verdict is the corroborated one
    assert _corroborate("supported", "WRITE_CLAIM_UNRECORDED", [1], f, recs)[0]


def test_malformed_cited_seqs_never_raises() -> None:
    for bad in (None, 7, "9", [True, "x", 9]):
        payload = {"verdicts": [{"finding_seq": 20, "verdict": "unsupported",
                                 "reason": "CLAIM_WAS_READ_NOT_WRITE", "cited_seqs": bad}],
                   "confidence": 0.9}
        rep = triage(_BUNDLE, client=_Fake(payload))
        assert rep.items[0].label in {"NEEDS_HUMAN", "RETRACTED"}
        assert rep.items[0].label != "RETRACTED" or rep.items[0].corroborated


# --- pgroup_escape adjudication: the model judges, the guard bounds the risk ---

from witness.analyst.triage import _corroborate_pgroup  # noqa: E402
from witness.models import MarkerRead, ProcEvent, ProcOp  # noqa: E402


def _esc_finding(seq: int, ev: int, sev: Severity = Severity.warn) -> Finding:
    return Finding(seq=seq, ts_wall=0.0, ts_mono=0.0, fkind=FindingKind.pgroup_escape,
                   severity=sev, evidence_seqs=[ev], detector_version="1.0")


def _proc_escape(seq: int) -> ProcEvent:
    return ProcEvent(seq=seq, ts_wall=0.0, ts_mono=0.0, op=ProcOp.escape, pid=10, ppid=9, exe="bash")


def _marker(seq: int) -> MarkerRead:
    return MarkerRead(seq=seq, ts_wall=0.0, ts_mono=0.0, peer_pid=10, peer_exe="python")


def test_pgroup_ordinary_detach_retractable_only_when_nothing_suspicious_follows() -> None:
    f = _esc_finding(3, 2)
    clean = {2: _proc_escape(2), 3: f}
    assert _corroborate_pgroup("unsupported", "ORDINARY_TOOL_PROCESS_DETACH", [2], f, clean)[0]
    dirty = {**clean, 5: _marker(5)}
    assert not _corroborate_pgroup("unsupported", "ORDINARY_TOOL_PROCESS_DETACH", [2], f, dirty)[0]


def test_pgroup_stop_severity_can_never_be_retracted() -> None:
    f = _esc_finding(3, 2, Severity.stop)
    recs = {2: _proc_escape(2), 3: f}
    assert not _corroborate_pgroup("unsupported", "ORDINARY_TOOL_PROCESS_DETACH", [2], f, recs)[0]


def test_pgroup_confirmation_needs_correlated_evidence() -> None:
    f = _esc_finding(3, 2)
    recs = {2: _proc_escape(2), 3: f}
    assert not _corroborate_pgroup("supported", "ESCAPED_PROCESS_ACTIVITY", [2], f, recs)[0]
    recs[5] = _marker(5)
    assert _corroborate_pgroup("supported", "ESCAPED_PROCESS_ACTIVITY", [2, 5], f, recs)[0]


def test_pgroup_cited_seq_must_exist() -> None:
    f = _esc_finding(3, 2)
    assert not _corroborate_pgroup("unsupported", "ORDINARY_TOOL_PROCESS_DETACH", [999], f, {2: _proc_escape(2), 3: f})[0]


def test_pgroup_unsupported_is_never_a_retraction() -> None:
    from witness.analyst.triage import _label
    assert _label("unsupported", True, FindingKind.pgroup_escape) == "LIKELY_BENIGN"
    assert _label("unsupported", True, FindingKind.mismatch) == "RETRACTED"
    assert _label("unsupported", False, FindingKind.pgroup_escape) == "NEEDS_HUMAN"


def test_bare_name_alias_must_be_unique() -> None:
    recs = {1: _claim(1, ClaimTool.write, ["config.py"]), 2: _fs(2, "a/config.py"), 3: _fs(3, "b/config.py")}
    f = _finding([1, 2, 3])
    assert not _corroborate("unsupported", "PATH_ALIAS_SAME_FILE", [1, 2], f, recs)[0]
