"""`witness watch` end to end: runs the REAL CLI command as a subprocess
against a real frozen bundle in replay mode (fast --speed so the test
doesn't take long) -- asserts real output lines appear, not a mock.
Live-tail mode is exercised manually (see cli.py's `watch` docstring);
this test covers the replay path, which is deterministic and fast.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_BUNDLE = REPO_ROOT / "runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl"


def test_watch_replay_prints_real_records_and_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "witness.cli", "watch", str(_REAL_BUNDLE), "--speed", "0"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # Real, specific content from this exact bundle -- not a generic string.
    assert "manifest run=20261027-011548-7dca" in out
    assert "#12" in out and "marker_read" in out
    assert "finding=mismatch" in out
    assert "receipt signed" in out


def test_watch_requires_a_real_path() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "witness.cli", "watch", "/no/such/bundle.jsonl", "--speed", "0"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
