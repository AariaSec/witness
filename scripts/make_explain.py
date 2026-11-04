"""Store real Meta-model read-outs next to console bundles, for the console's "check every citation in your browser" panel.

For each bundle it calls witness's own analyst (`analyst.run._live_report`) with each requested provider, keeps the first
successful call (attempt count recorded), and writes console/public/bundles/<name>.explain.json:
  { "bundle": ..., "readouts": [ { provider, model_id, generated_at, wall_s, attempts, response_sha256,
                                    python_check: {cites, exist, fit}, report: {...Report fields...} } ] }
The read-out is stored output of a real call and sits OUTSIDE the signed chain; the console shows it as such and verifies
each citation against the signed record in the browser. `python_check` is the same score meta_bench.py computes, so the
browser's counts can be cross-checked (console/tests/citations.test.ts).

    .venv/bin/python scripts/make_explain.py --bundle unprompted-readme-injection --providers meta baseten
Keys/endpoints are read by witness's own clients; this script never reads or prints them.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from witness.analyst.client import LLMClientError
from witness.analyst.run import _PROMPT_PATH_DEFAULT, _live_report
from witness.cli import _resolve_analyst_client
from witness.ledger import read_ledger

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "console/public/bundles"
_spec = importlib.util.spec_from_file_location("meta_bench", Path(__file__).with_name("meta_bench.py"))
bench = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(bench)  # type: ignore[union-attr]
LABEL = {"meta": "Muse Spark 1.3 (Meta Model API)", "baseten": "Muse Spark Open (Baseten, open-weight)", "glimmer": "Muse Glimmer 30B (Modal GPU, open-weight)"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, help="name under console/public/bundles (without .jsonl)")
    ap.add_argument("--providers", nargs="+", default=["meta", "baseten"])
    a = ap.parse_args()
    path = BUNDLES / f"{a.bundle}.jsonl"
    recs = read_ledger(path)
    out_path = BUNDLES / f"{a.bundle}.explain.json"
    existing = json.loads(out_path.read_text()) if out_path.exists() else {"bundle": f"bundles/{a.bundle}.jsonl", "readouts": []}
    for prov in a.providers:
        client = _resolve_analyst_client(prov)
        if client is None:
            print(prov, "no client; skipped")
            continue
        client._max_tokens = max(getattr(client, "_max_tokens", 0), 16000) if prov != "glimmer" else client._max_tokens
        client._timeout_s = 240
        for attempt in range(1, 4):
            t0 = time.time()
            try:
                rep = _live_report(recs, client, _PROMPT_PATH_DEFAULT, getattr(client, "_model", prov))
            except LLMClientError as exc:
                print(prov, "attempt", attempt, "failed:", str(exc)[:100])
                continue
            wall = round(time.time() - t0, 1)
            row = bench.score(path, recs, rep)
            body = json.loads(rep.model_dump_json())
            existing["readouts"] = [r for r in existing["readouts"] if r["provider"] != prov] + [{
                "provider": prov, "label": LABEL[prov], "model_id": rep.model_id,
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "wall_s": wall, "attempts": attempt,
                "response_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(),
                "python_check": {"cites": row["n_cites"], "exist": round((row["cite_exist"] or 0) * row["n_cites"]),
                                 "fit": round((row["cite_fit"] or 0) * row["n_cites"])},
                "report": body}]
            print(prov, "ok", wall, "s", row["n_cites"], "cites")
            break
    out_path.write_text(json.dumps(existing, indent=1))


if __name__ == "__main__":
    main()
