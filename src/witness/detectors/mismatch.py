"""Detector: reported-vs-recorded mismatch.

Accumulates the set of paths the assistant *claimed* (via
`AssistantClaim.claimed_paths`) against the set of paths independently
*recorded* (via `FsEvent`), and the claimed vs. recorded destination
hosts (`claimed_hosts` vs `OutboundPost.dest`). The comparison only fires
at `run_end` — a single finding, evaluated once the full claim/record
sets for the session are known — rather than on every partial mismatch
mid-stream (which would fire spuriously whenever ordering between a claim
and its corresponding event merely differs).
"""

from __future__ import annotations

from dataclasses import replace

from witness.detectors._state import DETECTOR_VERSION, DetectorState
from witness.models import Finding, FindingKind, FsOp, Kind, Record, Severity


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    if rec.kind == Kind.assistant_claim:
        state = replace(
            state,
            claimed_paths=state.claimed_paths | set(rec.claimed_paths),
            claimed_path_seqs=(
                (*state.claimed_path_seqs, rec.seq)
                if rec.claimed_paths
                else state.claimed_path_seqs
            ),
            claimed_hosts=state.claimed_hosts | set(rec.claimed_hosts),
            claimed_host_seqs=(
                (*state.claimed_host_seqs, rec.seq)
                if rec.claimed_hosts
                else state.claimed_host_seqs
            ),
        )
        return state, []

    if rec.kind == Kind.fs_event and rec.op in (FsOp.create, FsOp.modify):
        state = replace(
            state,
            recorded_paths=state.recorded_paths | {rec.path},
            recorded_path_seqs=(*state.recorded_path_seqs, rec.seq),
        )
        return state, []

    if rec.kind == Kind.outbound_post:
        state = replace(
            state,
            recorded_hosts=state.recorded_hosts | {rec.dest},
            recorded_host_seqs=(*state.recorded_host_seqs, rec.seq),
        )
        return state, []

    if rec.kind == Kind.run_end and not state.mismatch_fired:
        findings: list[Finding] = []
        claimed_not_recorded = state.claimed_paths - state.recorded_paths
        claimed_hosts_not_recorded = state.claimed_hosts - state.recorded_hosts
        if claimed_not_recorded or claimed_hosts_not_recorded:
            evidence = sorted(
                set(state.claimed_path_seqs)
                | set(state.recorded_path_seqs)
                | set(state.claimed_host_seqs)
                | set(state.recorded_host_seqs)
            )
            findings.append(
                Finding(
                    fkind=FindingKind.mismatch,
                    severity=Severity.warn,
                    evidence_seqs=evidence,
                    detector_version=DETECTOR_VERSION,
                )
            )
        state = replace(state, mismatch_fired=True)
        return state, findings

    return state, []


__all__ = ["evaluate"]
