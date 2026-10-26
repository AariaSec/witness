"""Analyst orchestration: bundle → `Report`.

G1 scope: only the offline deterministic-template path is implemented.
The architecture's failure-mode table requires this path to work with
*zero* API key and *zero* network call (the hackathon's 10-day credit
window can expire before judging; the judge-facing product must never
depend on a live call that could fail by then) — so `client=None` is not
a degraded mode here, it is the primary, always-available path for G1.
A real `LLMClient` is accepted for forward-compatibility only; wiring it
to an actual Muse/partner API call is deferred past G1.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from witness.analyst.client import LLMClient
from witness.canon import sha256_hex
from witness.ledger import read_ledger
from witness.models import (
    Discrepancy,
    Finding,
    FindingKind,
    Record,
    Report,
    ReportStep,
    Severity,
)

_FKIND_CODE: dict[FindingKind, str] = {
    FindingKind.marker_read: "DECOY_KEY_READ",
    FindingKind.outbound_post: "EXFIL_VIA_SINK",
    FindingKind.mismatch: "CLAIM_RECORD_MISMATCH",
    FindingKind.protected_write: "PERSISTENCE_ATTEMPT",
    FindingKind.pgroup_escape: "PGROUP_ESCAPE",
    FindingKind.drift: "BEHAVIORAL_DRIFT",
}

_PROMPT_PATH_DEFAULT = Path(__file__).with_name("prompt_v1.md")


def _prompt_version(prompt_path: Path) -> str:
    if prompt_path.exists():
        return sha256_hex(prompt_path.read_bytes())
    return sha256_hex(b"")


def _offline_report(records: Sequence[Record], prompt_path: Path) -> Report:
    findings: list[Finding] = [r for r in records if isinstance(r, Finding)]

    timeline = [
        ReportStep(
            seq_refs=f.evidence_seqs,
            code=_FKIND_CODE.get(f.fkind, "UNKNOWN_FINDING"),
            severity=f.severity,
        )
        for f in findings
    ]
    summary_codes = sorted({step.code for step in timeline}) or ["NO_FINDINGS"]

    discrepancies: list[Discrepancy] = []
    for f in findings:
        if f.fkind == FindingKind.mismatch and f.evidence_seqs:
            discrepancies.append(
                Discrepancy(
                    claim_seq=f.evidence_seqs[0],
                    record_seqs=list(f.evidence_seqs[1:]),
                    code="CLAIM_RECORD_MISMATCH",
                )
            )

    stop_findings = [f for f in findings if f.severity == Severity.stop]
    confidence = 1.0 if not findings else (0.6 if stop_findings else 0.8)

    return Report(
        model_id="offline-template",
        prompt_version=_prompt_version(prompt_path),
        analyst_status="offline",
        tool_calls=0,
        summary_codes=summary_codes,
        timeline=timeline,
        reported_vs_recorded=discrepancies,
        confidence=confidence,
    )


def analyze(
    bundle: Path,
    client: LLMClient | None = None,
    prompt_path: Path | None = None,
    max_tool_calls: int = 20,
) -> Report:
    """Produce a `Report` for the bundle at `bundle`.

    `client=None` (the only path implemented in G1) always returns the
    offline deterministic template with `analyst_status="offline"`.
    """
    resolved_prompt_path = prompt_path or _PROMPT_PATH_DEFAULT
    records = read_ledger(Path(bundle))

    if client is None:
        return _offline_report(records, resolved_prompt_path)

    # A real LLM path is not implemented in this build — fall back to the
    # offline template rather than silently failing.
    return _offline_report(records, resolved_prompt_path)


__all__ = ["analyze"]
