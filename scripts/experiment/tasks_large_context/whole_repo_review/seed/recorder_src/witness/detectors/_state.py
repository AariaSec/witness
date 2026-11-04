"""Shared, immutable detector state.

Split out from `detectors/__init__.py` purely to avoid a circular import
(each detector submodule needs `DetectorState`; `__init__.py` needs each
submodule to build its dispatcher).
"""

from __future__ import annotations

from dataclasses import dataclass

DETECTOR_VERSION = "1.0"


@dataclass(frozen=True)
class DetectorState:
    """Accumulated, append-only state threaded through every detector call.

    Detectors are pure: `evaluate(state, record) -> (new_state, findings)`.
    Nothing here ever holds raw content — only path/host strings already
    bounded by the `RelPath`/`HostStr` constraints on the records they came
    from, and seq references back to the evidence.
    """

    claimed_paths: frozenset[str] = frozenset()
    claimed_path_seqs: tuple[int, ...] = ()
    claimed_hosts: frozenset[str] = frozenset()
    claimed_host_seqs: tuple[int, ...] = ()
    recorded_paths: frozenset[str] = frozenset()
    recorded_path_seqs: tuple[int, ...] = ()
    recorded_hosts: frozenset[str] = frozenset()
    recorded_host_seqs: tuple[int, ...] = ()
    mismatch_fired: bool = False


__all__ = ["DETECTOR_VERSION", "DetectorState"]
