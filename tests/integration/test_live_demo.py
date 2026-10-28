"""`scripts/live_demo.py`: the live-demo launcher a presenter runs so a real
recording + `witness watch` + the hosted console line up for an unscripted
demo moment. Runs the REAL script as a subprocess with
`WITNESS_LIVE_DEMO_NO_OPEN=1` so it never opens a real terminal window or
browser under pytest -- this is a real end-to-end recording, just with the
GUI side effects suppressed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "live_demo.py"


@pytest.mark.skipif(sys.platform == "win32", reason="script targets macOS Terminal.app automation")
def test_live_demo_records_a_real_session_and_finds_its_run_dir() -> None:
    env = {**os.environ, "WITNESS_LIVE_DEMO_NO_OPEN": "1"}
    runs_dir = REPO_ROOT / "runs"
    before = {p.name for p in runs_dir.iterdir() if p.is_dir()} if runs_dir.is_dir() else set()

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "exfil"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert "Run directory: " in result.stdout, result.stdout
    assert "WITNESS_LIVE_DEMO_NO_OPEN set" in result.stdout, result.stdout
    assert "Done. Bundle: " in result.stdout, result.stdout

    run_dir_line = next(line for line in result.stdout.splitlines() if line.startswith("Run directory: "))
    run_dir = Path(run_dir_line.removeprefix("Run directory: "))
    assert run_dir.is_dir()
    assert (run_dir / "bundle.jsonl").is_file()
    assert (run_dir / "ledger.jsonl").is_file()

    after = {p.name for p in runs_dir.iterdir() if p.is_dir()}
    assert run_dir.name in after - before, "script must create a genuinely new run dir, not reuse one"

    # cleanup: this test creates a real, gitignored scratch run dir
    import shutil

    shutil.rmtree(run_dir, ignore_errors=True)
