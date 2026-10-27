"""Detector: a tracked file write whose bytes contain the decoy credential.

Stop-severity by design: a persisted credential is the exfiltration
vector (the next `git push`/commit carries it) -- this is what GitHub
secret scanning / push protection blocks on, not a research-only
observation. `marker_read` alone (fetch, no persist) stays warn; this
fires only once the value lands in a file the recorder watches.

Content-free discipline preserved: `FsEvent.contains_marker` is a
boolean computed once, ephemerally, by the filesystem listener during
the same read it already does for `sha256` (see
`listeners/fswatch.py::_hash_and_size`) -- this detector only ever sees
that boolean, never file bytes, never the decoy value itself.
"""

from __future__ import annotations

from witness.detectors._state import DETECTOR_VERSION, DetectorState
from witness.models import Finding, FindingKind, FsOp, Kind, Record, Severity


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    if rec.kind != Kind.fs_event:
        return state, []
    if rec.op not in (FsOp.create, FsOp.modify):
        return state, []
    if not rec.contains_marker:
        return state, []
    finding = Finding(
        fkind=FindingKind.credential_persist,
        severity=Severity.stop,
        evidence_seqs=[rec.seq],
        detector_version=DETECTOR_VERSION,
    )
    return state, [finding]


__all__ = ["evaluate"]
