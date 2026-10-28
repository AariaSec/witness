#!/usr/bin/env python3
"""Compute DRIFT_BASELINE for witness.detectors.drift from real, committed
bundles -- offline, deliberate, never run automatically at runtime.

Training set v2 (2026-10-27, real-only): the original v1 baseline mixed 5
SYNTHETIC `sim_agent` sessions (sub-millisecond scripted gaps) with only 2
real ones -- holdout validation showed the one feature with enough
training variance to score (median_gap_ms) was actually just detecting
"real LLM-latency session vs. scripted one," not benign vs. malicious.
Fixed by recording 8 MORE real sessions specifically for this baseline
(`corpus/benign-real/`, via `witness record-muse` on the existing
control_* task prompts -- real ordinary engineering tasks, no decoy
involved) and dropping the 5 synthetic ones entirely. Training set is now
10 real sessions: the 8 new ones plus the two ORIGINAL flagship proofs
(pre-dating the receipt v0.2 fix, so distinct artifacts from the two
CURRENT flagship proofs, which stay held-out and are never touched by
this script).

Usage:
    python3 scripts/compute_drift_baseline.py
Prints the (median, MAD) per feature to paste into drift.py's
DRIFT_BASELINE by hand -- deliberately manual, so a baseline change is a
reviewed diff, not a silent runtime recomputation.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from witness.detectors.drift import _scalar_features, session_shape  # noqa: E402
from witness.ledger import read_ledger  # noqa: E402

TRAIN_BUNDLES = [
    *sorted((REPO_ROOT / "corpus" / "benign-real").glob("*.jsonl")),
    REPO_ROOT
    / "runs"
    / "frozen"
    / "muse-real-agent-proof-20261026-185538-7c88"
    / "bundle.jsonl",
    REPO_ROOT
    / "runs"
    / "frozen"
    / "claude-real-agent-proof-20261027-004840-aa8e"
    / "bundle.jsonl",
]


def mad(values: list[float], med: float) -> float:
    return statistics.median([abs(v - med) for v in values])


def main() -> int:
    per_feature: dict[str, list[float]] = {}
    for path in TRAIN_BUNDLES:
        records = read_ledger(path)
        shape = session_shape(records)
        features = _scalar_features(shape)
        print(f"{path.relative_to(REPO_ROOT)}: {features}")
        for name, value in features.items():
            per_feature.setdefault(name, []).append(value)

    print("\nDRIFT_BASELINE = {")
    for name, values in per_feature.items():
        med = statistics.median(values)
        m = mad(values, med)
        print(f'    "{name}": ({med}, {m}),  # values={values}')
    print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
