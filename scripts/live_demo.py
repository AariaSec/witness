#!/usr/bin/env python3
"""live_demo.py -- one command that sets up the real, unscripted live-demo
moment: start a REAL recording in the background, tail it live in a second
terminal window with `witness watch`, and open the live console so the
finished bundle can be dragged on as soon as it's ready.

Nothing here is simulated differently from the rest of the project: this
calls the exact same `witness.demo.run_demo` function `witness demo` uses,
just with the run directory captured up front so `witness watch` can tail
it WHILE it's being written, instead of only after it's done.

Usage:
    python3 scripts/live_demo.py [scenario]

Default scenario is "credential_persist" (the one with a real stop_pgroup
action -- the most dramatic live moment: a `witness watch` STOP line and
the console's receipt panel flipping to "stopped" at the same instant).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSOLE_URL = "https://aariasec.github.io/witness/"


def _existing_run_dirs(runs_dir: Path) -> set[str]:
    if not runs_dir.is_dir():
        return set()
    return {p.name for p in runs_dir.iterdir() if p.is_dir()}


def _open_terminal_running(command: str) -> bool:
    """macOS only: open a new Terminal.app window running `command`.
    Returns False (never raises) if this isn't possible here -- the
    caller falls back to printing the command for the operator to run
    by hand in a second window."""
    if sys.platform != "darwin":
        return False
    script = f'tell application "Terminal" to do script "{command}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def main() -> int:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "credential_persist"
    runs_dir = REPO_ROOT / "runs"
    before = _existing_run_dirs(runs_dir)

    print(f"== witness live demo (scenario: {scenario}) ==")
    print("Starting a REAL recording in the background...")

    rec = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"from witness.demo.run_demo import run_demo; run_demo(scenario={scenario!r})",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    run_dir: Path | None = None
    for _ in range(100):  # ~10s max wait for the run dir to appear
        new = _existing_run_dirs(runs_dir) - before
        if new:
            run_dir = runs_dir / sorted(new)[0]
            break
        time.sleep(0.1)

    if run_dir is None:
        print("Could not find the new run directory in time -- the recording", file=sys.stderr)
        print("may still be starting up. Check `runs/` manually.", file=sys.stderr)
        rec.wait()
        return 1

    ledger = run_dir / "ledger.jsonl"
    watch_cmd = f"cd {REPO_ROOT} && .venv/bin/witness watch {ledger}"
    print(f"Run directory: {run_dir}")
    print(f"Live-tailing command: {watch_cmd}")

    no_open = bool(os.environ.get("WITNESS_LIVE_DEMO_NO_OPEN"))
    if no_open:
        print("(WITNESS_LIVE_DEMO_NO_OPEN set -- not opening a terminal or browser)")
    elif _open_terminal_running(watch_cmd):
        print("Opened a second Terminal window tailing it live.")
    else:
        print("Could not auto-open a second terminal -- run this yourself in another window:")
        print(f"  {watch_cmd}")

    if not no_open:
        print(f"Opening the live console ({CONSOLE_URL}) -- drag the finished bundle onto it once ready.")
        subprocess.run(["open", CONSOLE_URL], check=False)

    print("Recording in progress -- waiting for it to finish...")
    rec.wait()
    bundle = run_dir / "bundle.jsonl"
    print(f"Done. Bundle: {bundle}")
    print("Drag that file onto the console window now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
