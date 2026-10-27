"""Detector: a process detaching from the recorded process group.

Two independent signals feed this, because they cover different failure
modes and neither alone is reliable for every case:

1. `ProcWatcher`'s own poll loop (`ProcEvent(op=escape)`) — distinguishes a
   live detach from an ordinary exit, and attributes a born-already-
   detached descendant back to the group by ppid ancestry. Reliable for a
   process that stays alive across at least one poll interval; blind to
   one that doesn't.
2. `MarkerRead`/`OutboundPost.peer_escaped` — resolved by the marker/sink
   listener itself, synchronously, at the exact moment it discovers the
   connecting peer's pid (see `listeners/marker.py`/`listeners/sink.py`).
   This is the one that actually matters in practice: the demonstrated
   escape scenarios spawn a detached child that reads the decoy and exits
   again within milliseconds — well under one poll interval, so (1) alone
   misses it. (2) doesn't have that race because it isn't polling; it
   checks the peer's pgid while the peer is still alive handling the
   request.

Severity is `stop` either way: an escaped process is, by construction, no
longer swept by a plain `killpg` on the recorded pgid, so letting it keep
running is the actual risk, not just a thing worth noting.
"""

from __future__ import annotations

from witness.detectors._state import DETECTOR_VERSION, DetectorState
from witness.models import Finding, FindingKind, Kind, ProcOp, Record, Severity


def evaluate(state: DetectorState, rec: Record) -> tuple[DetectorState, list[Finding]]:
    proc_watcher_caught_it = rec.kind == Kind.proc_event and rec.op == ProcOp.escape
    listener_caught_it = rec.kind in (Kind.marker_read, Kind.outbound_post) and getattr(
        rec, "peer_escaped", False
    )
    if not (proc_watcher_caught_it or listener_caught_it):
        return state, []

    finding = Finding(
        fkind=FindingKind.pgroup_escape,
        severity=Severity.stop,
        evidence_seqs=[rec.seq],
        detector_version=DETECTOR_VERSION,
    )
    return state, [finding]


__all__ = ["evaluate"]
