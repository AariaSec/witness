"""Run pgroup_escape triage over every real session in the unprompted batch and count how the model annotates the
warnings, per arm. The 'none' arm sessions never touched the decoy or wrote a credential, so their escape
warnings are benign by construction; that is the real false-alarm population. Keys are read by witness's own
clients; this script never reads or prints them.
Usage: .venv/bin/python scripts/triage_batch.py --provider meta --out runs/frozen/triage-unprompted-<date>/"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from witness.analyst.triage import triage_records
from witness.cli import _resolve_analyst_client
from witness.ledger import read_ledger
from witness.models import Finding, FindingKind

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="meta")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    client = _resolve_analyst_client(a.provider)
    if client is None:
        raise SystemExit("no live client (offline); not writing results")
    rows = [r for r in csv.DictReader(open(ROOT / "scripts/experiment/results_unprompted.csv")) if r["exit_code"] != "RECORD_FAILED"]
    out = []
    for r in rows:
        bpath = next((b for b in (ROOT / "runs/frozen" / "unprompted-experiment-20261103" / r["run_id"] / "bundle.jsonl",
                                  Path("/tmp/witness-experiment-runs-unprompted") / r["run_id"] / "bundle.jsonl") if b.exists()), None)
        if bpath is None:
            continue
        recs = read_ledger(bpath)
        n_warn = sum(isinstance(x, Finding) and x.fkind == FindingKind.pgroup_escape and x.severity.value == "warn" for x in recs)
        if not n_warn:
            continue
        for attempt in (1, 2, 3):   # a failed or timed-out live call falls back to offline; retry before recording that
            rep = triage_records(recs, client=client)
            if rep.status == "ok":
                break
        for it in rep.items:
            if it.fkind == "pgroup_escape":
                out.append({"run_id": r["run_id"], "task": r["task"], "pull": r["pull_level"], "status": rep.status, "attempts": attempt,
                            "finding_seq": it.finding_seq, "model_verdict": it.model_verdict, "reason": it.reason,
                            "label": it.label, "corroborated": it.corroborated, "note": it.note})
        print(r["task"], r["run_id"], rep.status, Counter(i.label for i in rep.items if i.fkind == "pgroup_escape"), flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"results_{a.provider}.json").write_text(json.dumps(out, indent=1))
    by = defaultdict(Counter)
    for x in out:
        by[x["pull"]][x["label"] if x["status"] == "ok" else "OFFLINE"] += 1
    for arm in ("none", "code", "docs"):
        print(arm, dict(by[arm]), "total", sum(by[arm].values()))


if __name__ == "__main__":
    main()
