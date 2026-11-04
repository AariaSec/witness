"""Experimental behavioral-signal detector — STUB for G1.

Per the final-plan audit (patch #4): a real drift signal needs a
train/holdout split and a pre-registered threshold before it can fire
without producing false alarms a judge (or a user) would immediately
spot. That scoring work is deferred past G1. This module therefore always
returns no finding — it does not fake a signal, and `drift_score`/
`session_shape` are honest placeholders, not wired into `evaluate`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from witness.detectors._state import DetectorState
from witness.models import Finding, Record


class SessionShape(TypedDict, total=False):
    """Placeholder shape summary (tool-mix histogram, destination novelty,
    inter-event gap stats). Populated for real once a train/holdout split
    exists; empty for now."""

    tool_mix: dict[str, int]
    dest_novelty: float
    inter_event_gaps_ms: list[float]


def session_shape(records: Sequence[Record]) -> SessionShape:
    """STUB: returns an empty shape. Real session-shape extraction is
    deferred past G1 (needs a baseline corpus to be meaningful)."""
    return SessionShape()


def drift_score(baseline: SessionShape, current: SessionShape) -> float:
    """STUB: always returns 0.0 (no drift). A robust z-score over
    median/MAD is deferred until a train/holdout split exists — see
    final-plan patch #4. Never fabricates a nonzero signal."""
    return 0.0


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    """Always returns no finding. This is the experimental detector's G1
    contract: stubbed, not faked."""
    return state, []


__all__ = ["SessionShape", "drift_score", "evaluate", "session_shape"]
