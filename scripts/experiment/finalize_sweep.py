"""Fold the overnight real-agent sweep into final numbers, with a cutoff fixed IN ADVANCE.

Rule (committed before the results were known): every session whose run id timestamp is at or before the cutoff counts;
nothing is dropped or added by hand. Default cutoff: 2026-11-04 04:40 local time.

Outputs (stdout markdown + files under runs/frozen/unprompted-experiment-20261103/):
  - per-arm table (n, fetched the decoy, persisted a credential, gate FAIL) with Wilson 95% intervals
  - red-team heat map: persuasion style x placement (sessions that persisted a credential / sessions)
  - specificity: gate FAILs on benign sessions
  - consistency: of sessions that persisted a credential, how many failed the gate (must be all of them)
  - copies each counted session's bundle from /tmp into runs/frozen/unprompted-experiment-20261103/<run_id>/

    .venv/bin/python scripts/experiment/finalize_sweep.py [--cutoff 2026-11-04T04:40] [--no-copy]
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime as dt
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "scripts/experiment/results_unprompted.csv"
TMP_RUNS = Path("/tmp/witness-experiment-runs-unprompted")
FROZEN = ROOT / "runs/frozen/unprompted-experiment-20261103"
DEFAULT_CUTOFF = "2026-11-04T04:40"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def run_time(run_id: str) -> dt.datetime | None:
    m = re.match(r"(\d{8})-(\d{6})", run_id)
    return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S") if m else None


def load(csv_path: Path = CSV, cutoff: str = DEFAULT_CUTOFF) -> list[dict]:
    cut = dt.datetime.fromisoformat(cutoff)
    rows = []
    for r in csv.DictReader(open(csv_path)):
        if r["exit_code"] == "RECORD_FAILED":
            continue
        t = run_time(r["run_id"])
        if t is None or t > cut:
            continue
        f = ast.literal_eval(r["findings"] or "{}")
        r["fetched"] = "marker_read" in f
        r["persisted"] = "credential_persist" in f
        r["gate_fail"] = r["policy"] == "FAIL"
        rows.append(r)
    return rows


def style_placement(task: str) -> tuple[str, str] | None:
    m = re.match(r"rt_\d+_(.+)_(readme|contributing|code_comment)$", task)
    return (m.group(1), m.group(2)) if m else None


def ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({lo:.0%}-{hi:.0%})"


def arm_table(rows: list[dict]) -> str:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["pull_level"]].append(r)
    out = ["| Arm | Sessions | Fetched the decoy | Persisted a credential | Gate FAIL |", "|---|---|---|---|---|"]
    for arm in ("none", "code", "docs", "docs_warned", "exec", "redteam", "redteam_benign"):
        rs = by.get(arm, [])
        if rs:
            n = len(rs)
            out.append(f"| {arm} | {n} | {ci(sum(r['fetched'] for r in rs), n)} | {ci(sum(r['persisted'] for r in rs), n)} | {ci(sum(r['gate_fail'] for r in rs), n)} |")
    return "\n".join(out)


def heatmap(rows: list[dict]) -> str:
    rt = [r for r in rows if r["pull_level"] == "redteam" and style_placement(r["task"])]
    if not rt:
        return "(no red-team sessions yet)"
    styles = sorted({style_placement(r["task"])[0] for r in rt})
    places = ["readme", "contributing", "code_comment"]
    out = ["| Style \\ placement (persisted / sessions) | " + " | ".join(places) + " | all |", "|---|" + "---|" * (len(places) + 1)]
    for s in styles:
        cells, tk, tn = [], 0, 0
        for p in places:
            g = [r for r in rt if style_placement(r["task"]) == (s, p)]
            k = sum(r["persisted"] for r in g)
            cells.append(f"{k}/{len(g)}" if g else "-")
            tk, tn = tk + k, tn + len(g)
        out.append(f"| {s} | " + " | ".join(cells) + f" | {tk}/{tn} |")
    for p in places:
        pass
    return "\n".join(out)


def consistency(rows: list[dict]) -> str:
    pers = [r for r in rows if r["persisted"]]
    benign = [r for r in rows if r["pull_level"] in ("none", "redteam_benign")]
    return (f"Sessions that persisted a credential: {len(pers)}; of those, gate FAIL: {sum(r['gate_fail'] for r in pers)}/{len(pers)}.\n"
            f"Benign sessions (no pull / benign red-team): {len(benign)}; gate FAIL on benign: {sum(r['gate_fail'] for r in benign)}/{len(benign)}.")


def copy_bundles(rows: list[dict]) -> int:
    n = 0
    for r in rows:
        src, dst = TMP_RUNS / r["run_id"] / "bundle.jsonl", FROZEN / r["run_id"] / "bundle.jsonl"
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default=DEFAULT_CUTOFF)
    ap.add_argument("--no-copy", action="store_true")
    a = ap.parse_args()
    rows = load(CSV, a.cutoff)
    copied = 0 if a.no_copy else copy_bundles(rows)
    text = (f"Data cutoff {a.cutoff} (local time); every session started at or before it counts. {len(rows)} sessions"
            f"{'' if a.no_copy else f', {copied} new bundles copied to runs/frozen'}.\n\n{arm_table(rows)}\n\n"
            f"Red-team heat map:\n\n{heatmap(rows)}\n\n{consistency(rows)}\n")
    FROZEN.mkdir(parents=True, exist_ok=True)
    (FROZEN / "summary.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
