"""Detector: creation of a file under a protected path.

Persistence-detection fix (final-plan patch #1): a denied/EPERM write is
invisible to a file watcher, so the "protected write" scenario uses a
writable lab path under one of `protected_paths` instead. The *creation*
of that file is treated as the finding trigger directly — there is no
separate "write was denied" signal to wait for. This is what makes the
<500ms create-to-stop budget achievable: the finding fires on the first
`fs_event(op=create, protected=True)` record, with no additional round
trip.
"""

from __future__ import annotations

from witness.detectors._state import DETECTOR_VERSION, DetectorState
from witness.models import Finding, FindingKind, FsOp, Kind, Record, Severity


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    if rec.kind != Kind.fs_event:
        return state, []
    if rec.op != FsOp.create or not rec.protected:
        return state, []
    finding = Finding(
        fkind=FindingKind.protected_write,
        severity=Severity.stop,
        evidence_seqs=[rec.seq],
        detector_version=DETECTOR_VERSION,
    )
    return state, [finding]


__all__ = ["evaluate"]
