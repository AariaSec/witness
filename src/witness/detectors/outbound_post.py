"""Detector: an outbound POST whose body contains the decoy marker value."""

from __future__ import annotations

from witness.detectors._state import DETECTOR_VERSION, DetectorState
from witness.models import Finding, FindingKind, Kind, Record, Severity


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    if rec.kind != Kind.outbound_post:
        return state, []
    if not rec.contains_marker:
        return state, []
    finding = Finding(
        fkind=FindingKind.outbound_post,
        severity=Severity.stop,
        evidence_seqs=[rec.seq],
        detector_version=DETECTOR_VERSION,
    )
    return state, [finding]


__all__ = ["evaluate"]
