"""Detector: any read of the decoy marker is itself the finding."""

from __future__ import annotations

from witness.detectors._state import DETECTOR_VERSION, DetectorState
from witness.models import Finding, FindingKind, Kind, Record, Severity


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    if rec.kind != Kind.marker_read:
        return state, []
    # Policy only closes the marker for a bare read (no stop_pgroup) — the
    # severity reflects that: a read alone is "warn", not "stop". Escalation
    # to "stop" happens via outbound_post once the decoy value is actually
    # exfiltrated.
    finding = Finding(
        fkind=FindingKind.marker_read,
        severity=Severity.warn,
        evidence_seqs=[rec.seq],
        detector_version=DETECTOR_VERSION,
    )
    return state, [finding]


__all__ = ["evaluate"]
