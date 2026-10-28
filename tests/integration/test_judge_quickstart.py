"""`scripts/judge_quickstart.sh`: the one script a judge runs end to end --
record -> verify -> open the console -- with no API key and no network
except the recorder's own loopback marker/sink.

Runs the REAL script as a subprocess against this checkout's own `.venv`
(the fast path -- `[1/4] Using existing .venv`, no re-provisioning), with
`WITNESS_QUICKSTART_NO_OPEN=1` so it never launches a real browser under
pytest. This is the actual script a judge runs, not a reimplementation of
its logic -- a bug in the sed/parsing would show up here.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "judge_quickstart.sh"


def test_script_is_syntactically_valid_bash() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="script is bash, not run on Windows CI")
def test_end_to_end_real_run_records_verifies_and_parses_the_bundle_path() -> None:
    env = {**os.environ, "WITNESS_QUICKSTART_NO_OPEN": "1"}
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert "Using existing .venv" in result.stdout, result.stdout
    assert "demo bundle: " in result.stdout, result.stdout
    assert "OK: " in result.stdout and "receipt_ok=True" in result.stdout, result.stdout
    assert "witness verify exit code: 2" in result.stdout, result.stdout
    assert "WITNESS_QUICKSTART_NO_OPEN set" in result.stdout, result.stdout

    bundle_line = next(line for line in result.stdout.splitlines() if line.startswith("demo bundle: "))
    bundle_path = REPO_ROOT / bundle_line.removeprefix("demo bundle: ")
    assert bundle_path.is_file(), f"parsed bundle path does not exist: {bundle_path}"
    assert bundle_path.name == "bundle.jsonl"
