"""Detector dispatcher.

`evaluate(state, record)` runs every detector (pure functions) over one
newly-appended ledger record and returns the updated combined state plus
any `Finding`s produced. The ledger writer calls this after every
`append()`; findings are themselves appended as ledger records.
"""

from __future__ import annotations

from witness.detectors import drift as _drift
from witness.detectors import (
    credential_persist,
    marker_read,
    mismatch,
    outbound_post,
    pgroup_escape,
    protected_write,
)
from witness.detectors._state import DETECTOR_VERSION, DetectorState
from witness.models import Finding, Record

_DETECTORS = (
    marker_read,
    outbound_post,
    protected_write,
    credential_persist,
    mismatch,
    pgroup_escape,
    _drift,
)


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    findings: list[Finding] = []
    for module in _DETECTORS:
        state, new_findings = module.evaluate(state, rec)
        findings.extend(new_findings)
    return state, findings


__all__ = ["DETECTOR_VERSION", "DetectorState", "evaluate"]
