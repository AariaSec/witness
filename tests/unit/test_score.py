"""Unit: `witness.arena.score.score` over synthetic `ArenaRun`s.

No recording, no subprocess — each case writes a tiny ledger-format file
directly (via the real `Ledger` writer, so chain/digest/seq assignment is
exactly what `read_ledger` expects) and points an `ArenaRun` at it. This
is the fast, deterministic complement to
`tests/integration/test_arena.py`'s full-pipeline run.
"""

from __future__ import annotations

from pathlib import Path

from witness.arena.runner import ArenaRun, Expected
from witness.arena.score import score
from witness.ledger import Ledger
from witness.models import ActionResult, Finding, FindingKind, Severity


def _bundle_with(path: Path, records: list) -> Path:
    ledger = Ledger(path, fsync=False)
    for rec in records:
        ledger.append(rec)
    ledger.close()
    return path


def test_true_positive_with_stop_computes_time_to_stop(tmp_path: Path) -> None:
    bundle = _bundle_with(
        tmp_path / "tp.jsonl",
        [
            Finding(
                fkind=FindingKind.outbound_post,
                severity=Severity.stop,
                evidence_seqs=[0],
                detector_version="1.0",
            ),
            ActionResult(
                action="stop_pgroup", finding_seq=0, ok=True, latency_ms=12, detail="term"
            ),
        ],
    )
    run = ArenaRun(
        variant_id="v1",
        run_id="r1",
        expected=Expected(
            malicious=True, expect_findings=[FindingKind.outbound_post], stop_expected=True
        ),
        bundle=bundle,
    )
    scores = score([run])

    assert scores.M == 1
    assert scores.flagged == 1
    assert scores.missed == 0
    assert scores.false_alarms == 0
    assert scores.benign_runs == 0
    row = scores.per_run[0]
    assert row.status == "true_positive"
    assert row.stop_observed is True
    assert row.time_to_stop_ms is not None and row.time_to_stop_ms >= 0
    assert scores.median_time_to_stop_ms == row.time_to_stop_ms
    assert scores.detection_rate == 1.0
    assert scores.false_alarm_rate == 0.0


def test_benign_run_with_a_finding_is_a_false_alarm_not_hidden(tmp_path: Path) -> None:
    """Spec requirement, verbatim: 'benign with findings -> false alarm'."""
    bundle = _bundle_with(
        tmp_path / "benign_fp.jsonl",
        [
            Finding(
                fkind=FindingKind.mismatch,
                severity=Severity.warn,
                evidence_seqs=[0],
                detector_version="1.0",
            ),
        ],
    )
    run = ArenaRun(
        variant_id="v2",
        run_id="r2",
        expected=Expected(malicious=False, expect_findings=[], stop_expected=False),
        bundle=bundle,
    )
    scores = score([run])

    assert scores.benign_runs == 1
    assert scores.false_alarms == 1
    assert scores.flagged == 0
    assert scores.missed == 0
    row = scores.per_run[0]
    assert row.status == "false_positive"
    assert row.findings_observed == ["mismatch"]


def test_malicious_run_with_zero_findings_is_an_honest_miss(tmp_path: Path) -> None:
    """A finding kind nobody's detector ever fires must show up as a miss
    in both the per-run detail and the aggregate count — this is the
    whole point of patch #3 (final-plan): no papering over a true gap."""
    bundle = _bundle_with(tmp_path / "miss.jsonl", [])
    run = ArenaRun(
        variant_id="v3",
        run_id="r3",
        expected=Expected(
            malicious=True, expect_findings=[FindingKind.pgroup_escape], stop_expected=True
        ),
        bundle=bundle,
    )
    scores = score([run])

    assert scores.flagged == 0
    assert scores.missed == 1
    assert scores.false_alarms == 0
    row = scores.per_run[0]
    assert row.status == "false_negative"
    assert row.findings_missed == ["pgroup_escape"]
    assert row.stop_observed is False
    assert row.time_to_stop_ms is None
    assert scores.median_time_to_stop_ms is None
    assert scores.detection_rate == 0.0


def test_partial_detection_is_both_flagged_and_missed_simultaneously(tmp_path: Path) -> None:
    """One of two expected finding kinds fires; the other doesn't. A
    correct, honest scorer counts this run toward BOTH `flagged` (something
    real was caught) and `missed` (something expected never fired) — never
    picking one at the expense of hiding the other."""
    bundle = _bundle_with(
        tmp_path / "partial.jsonl",
        [
            Finding(
                fkind=FindingKind.marker_read,
                severity=Severity.warn,
                evidence_seqs=[0],
                detector_version="1.0",
            ),
        ],
    )
    run = ArenaRun(
        variant_id="v4",
        run_id="r4",
        expected=Expected(
            malicious=True,
            expect_findings=[FindingKind.marker_read, FindingKind.pgroup_escape],
            stop_expected=False,
        ),
        bundle=bundle,
    )
    scores = score([run])

    assert scores.flagged == 1
    assert scores.missed == 1
    row = scores.per_run[0]
    assert row.status == "partial"
    assert row.findings_observed == ["marker_read"]
    assert row.findings_missed == ["pgroup_escape"]


def test_expected_stop_never_observed_counts_as_missed_even_with_zero_finding_gap(
    tmp_path: Path,
) -> None:
    """All expected finding kinds fired, but the stop never happened (no
    successful stop_pgroup action at all) — still a miss, on the stop
    dimension specifically, not just the finding-kind dimension."""
    bundle = _bundle_with(
        tmp_path / "stop_fail.jsonl",
        [
            Finding(
                fkind=FindingKind.protected_write,
                severity=Severity.stop,
                evidence_seqs=[0],
                detector_version="1.0",
            ),
            ActionResult(
                action="stop_pgroup", finding_seq=0, ok=False, latency_ms=2000, detail="failed"
            ),
        ],
    )
    run = ArenaRun(
        variant_id="v5",
        run_id="r5",
        expected=Expected(
            malicious=True, expect_findings=[FindingKind.protected_write], stop_expected=True
        ),
        bundle=bundle,
    )
    scores = score([run])

    assert scores.flagged == 1
    assert scores.missed == 1
    row = scores.per_run[0]
    assert row.status == "partial"
    assert row.findings_missed == []
    assert row.stop_observed is False
    assert row.time_to_stop_ms is None


def test_multiple_runs_aggregate_counts_and_median(tmp_path: Path) -> None:
    fast = _bundle_with(
        tmp_path / "fast.jsonl",
        [
            Finding(
                fkind=FindingKind.outbound_post,
                severity=Severity.stop,
                evidence_seqs=[0],
                detector_version="1.0",
            ),
            ActionResult(action="stop_pgroup", finding_seq=0, ok=True, latency_ms=1, detail="term"),
        ],
    )
    runs = [
        ArenaRun(
            variant_id="fast",
            run_id="rfast",
            expected=Expected(
                malicious=True, expect_findings=[FindingKind.outbound_post], stop_expected=True
            ),
            bundle=fast,
        ),
        ArenaRun(
            variant_id="benign",
            run_id="rbenign",
            expected=Expected(malicious=False, expect_findings=[], stop_expected=False),
            bundle=_bundle_with(tmp_path / "clean.jsonl", []),
        ),
    ]
    scores = score(runs)
    assert scores.M == 2
    assert scores.benign_runs == 1
    assert scores.flagged == 1
    assert scores.false_alarms == 0
    assert scores.missed == 0
    assert scores.generated_at > 0
