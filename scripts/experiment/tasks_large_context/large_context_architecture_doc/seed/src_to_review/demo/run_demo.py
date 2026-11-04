"""One-command demo: record `sim_agent` → bundle → print the bundle path.

No API key, no network except the recorder's own loopback-only marker/sink
— this is the "no Meta API key fallback path" the G1 exit criteria require
to work end-to-end.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from witness.bundle import build_bundle
from witness.cli import _run_record
from witness.config import RecordConfig


def run_demo(scenario: str = "exfil", runs_dir: Path | None = None) -> Path:
    runs_dir = Path(runs_dir) if runs_dir is not None else Path("runs")
    lab = Path(tempfile.mkdtemp(prefix="witness-demo-lab-"))
    config = RecordConfig(lab=lab, max_seconds=15)
    assistant_cmd = [sys.executable, "-m", "witness.demo.sim_agent", "--scenario", scenario]

    run_dir = _run_record(config, assistant_cmd, runs_dir)
    bundle_path = run_dir / "bundle.jsonl"
    build_bundle(run_dir, bundle_path)
    return bundle_path


if __name__ == "__main__":
    print(run_demo())
