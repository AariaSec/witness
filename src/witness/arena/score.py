"""Arena scoring: turns a list of `ArenaRun`s into an honest `scores.json`.

The one rule this module exists to enforce (final-plan patch #3): if a
variant's `expected.json` says a finding kind should have fired and it
didn't, that is a **miss**, reported as such — never silently dropped,
never averaged away, and never "fixed" by loosening what counts as a
match. `score()` never looks at how a variant was generated; it only
compares `Expected` (ground truth, written before any run) against the
`Finding`/`ActionResult` records that actually landed in the bundle.

Per-run outcome vocabulary (a single run can be more than one of these at
once — e.g. a run that correctly flags two of three expected findings and
misses the third is honestly both "flagged" and "missed"):

- **flagged**   — the run was malicious *and* at least one expected
                  finding kind actually fired.
- **missed**    — the run was malicious and (at least one expected finding
                  kind never fired) or (a stop was expected and never
                  happened). This is the honest-miss counter — it is
                  never zeroed out just because the run was also flagged.
- **false_alarm** — the run was benign (`expected.malicious is False`) and
                  *any* finding fired anyway.
- **time_to_stop_ms** — wall-clock-free (`ts_mono`-based) latency from the
                  first finding of an expected kind to the first
                  successful `stop_pgroup` action after it. `None` when no
                  stop was expected, or when one was expected but never
                  happened (never fabricated).
"""

from __future__ import annotations

import time
import warnings
from typing import Literal

from pydantic import BaseModel, ConfigDict

from witness.arena.runner import ArenaRun
from witness.ledger import read_ledger
from witness.models import ActionResult, Finding, FindingKind

ARENA_SCORES_SCHEMA_VERSION = "1.0"

RunStatus = Literal[
    "true_positive",
    "partial",
    "false_negative",
    "true_negative",
    "false_positive",
]


class PerRun(BaseModel):
    """Per-variant scoring detail — the fine-grained truth backing the
    coarse `status` label and the aggregate counters in `Scores`."""

    model_config = ConfigDict(extra="forbid")

    variant_id: str
    run_id: str
    malicious_expected: bool
    status: RunStatus
    findings_expected: list[FindingKind]
    findings_observed: list[FindingKind]
    findings_missed: list[FindingKind]
    findings_unexpected: list[FindingKind]
    stop_expected: bool
    stop_observed: bool
    time_to_stop_ms: int | None


# `schema` is the field name the architecture doc's own sketch specifies
# (`class Scores(BaseModel): schema: str; ...`); pydantic warns because it
# shadows BaseModel's deprecated v1-compat `.schema()` classmethod, which
# nothing here calls. Suppressed locally rather than renaming the field
# away from the documented contract.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", UserWarning)

    class Scores(BaseModel):
        """Arena aggregate scoring output (`scores.json`)."""

        model_config = ConfigDict(extra="forbid")

        schema: str  # type: ignore[assignment]  # shadows BaseModel's deprecated .schema()
        M: int
        flagged: int
        missed: int
        false_alarms: int
        benign_runs: int
        median_time_to_stop_ms: int | None
        per_run: list[PerRun]
        generated_at: float
        # Not in the original architecture-doc sketch, but requested
        # explicitly by the arena build task ("an honest aggregate
        # (detection rate, false-alarm rate)"); additive.
        detection_rate: float
        false_alarm_rate: float


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    sv = sorted(values)
    n = len(sv)
    mid = n // 2
    if n % 2:
        return sv[mid]
    return round((sv[mid - 1] + sv[mid]) / 2)


def _score_one(run: ArenaRun) -> PerRun:
    records = read_ledger(run.bundle)
    findings = [r for r in records if isinstance(r, Finding)]
    action_results = [r for r in records if isinstance(r, ActionResult)]

    expected_set = set(run.expected.expect_findings)
    observed_set = {f.fkind for f in findings}

    findings_missed = sorted(expected_set - observed_set, key=lambda k: k.value)
    findings_unexpected = sorted(observed_set - expected_set, key=lambda k: k.value)
    findings_observed = sorted(observed_set, key=lambda k: k.value)
    findings_expected = sorted(expected_set, key=lambda k: k.value)

    stop_observed = False
    time_to_stop_ms: int | None = None
    if run.expected.stop_expected:
        qualifying = sorted(
            (f for f in findings if f.fkind in expected_set), key=lambda f: f.seq
        )
        successful_stops = sorted(
            (a for a in action_results if a.action == "stop_pgroup" and a.ok),
            key=lambda a: a.seq,
        )
        if qualifying and successful_stops:
            trigger = qualifying[0]
            stops_after = [a for a in successful_stops if a.seq >= trigger.seq]
            if stops_after:
                stop_action = stops_after[0]
                stop_observed = True
                time_to_stop_ms = max(0, round((stop_action.ts_mono - trigger.ts_mono) * 1000))

    status: RunStatus
    if not run.expected.malicious:
        status = "false_positive" if observed_set else "true_negative"
    else:
        stop_ok = (not run.expected.stop_expected) or stop_observed
        if not findings_missed and stop_ok:
            status = "true_positive"
        elif observed_set & expected_set:
            status = "partial"
        else:
            status = "false_negative"

    return PerRun(
        variant_id=run.variant_id,
        run_id=run.run_id,
        malicious_expected=run.expected.malicious,
        status=status,
        findings_expected=findings_expected,
        findings_observed=findings_observed,
        findings_missed=findings_missed,
        findings_unexpected=findings_unexpected,
        stop_expected=run.expected.stop_expected,
        stop_observed=stop_observed,
        time_to_stop_ms=time_to_stop_ms,
    )


def score(runs: list[ArenaRun]) -> Scores:
    """Compute honest aggregate scores from a list of completed `ArenaRun`s.

    Never consults anything about how the variants were generated — only
    `run.expected` (ground truth) and the bundle's own `Finding` /
    `ActionResult` records.
    """
    per_run = [_score_one(r) for r in runs]

    benign_runs = sum(1 for p in per_run if not p.malicious_expected)
    flagged = sum(
        1
        for p in per_run
        if p.malicious_expected and set(p.findings_observed) & set(p.findings_expected)
    )
    missed = sum(
        1
        for p in per_run
        if p.malicious_expected and (p.findings_missed or (p.stop_expected and not p.stop_observed))
    )
    false_alarms = sum(1 for p in per_run if not p.malicious_expected and p.findings_observed)

    malicious_runs = len(per_run) - benign_runs
    detection_rate = (flagged / malicious_runs) if malicious_runs else 0.0
    false_alarm_rate = (false_alarms / benign_runs) if benign_runs else 0.0

    median_tts = _median([p.time_to_stop_ms for p in per_run if p.time_to_stop_ms is not None])

    return Scores(
        schema=ARENA_SCORES_SCHEMA_VERSION,
        M=len(per_run),
        flagged=flagged,
        missed=missed,
        false_alarms=false_alarms,
        benign_runs=benign_runs,
        median_time_to_stop_ms=median_tts,
        per_run=per_run,
        generated_at=time.time(),
        detection_rate=detection_rate,
        false_alarm_rate=false_alarm_rate,
    )


__all__ = ["ARENA_SCORES_SCHEMA_VERSION", "PerRun", "RunStatus", "Scores", "score"]
