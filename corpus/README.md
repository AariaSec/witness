# Benign corpus

Real, independently recorded bundles from `witness demo --scenario benign`
runs — `src/witness/demo/sim_agent.py`'s benign scenario, which performs
ordinary, non-malicious file activity and never touches the decoy
credential. Each file here is a complete, chain-verified, receipt-signed
bundle from its own separate `witness record` run (own `run_id`, own
process, own ports) — not five copies of one run.

| File | Records | Findings | `receipt_ok` |
|------|---------|----------|--------------|
| b01.jsonl – b05.jsonl | 19 each | `{}` (zero) | `True` |

Reproduce: `witness record --lab <tmp> --max-seconds 15 --runs-dir <out> -- python -m witness.demo.sim_agent --scenario benign`, then `witness bundle <run_dir> --out bundle.jsonl` and `witness verify bundle.jsonl`.

**What this does and doesn't prove.** Five runs of the same deterministic
scenario give zero false alarms across five independent recordings — real,
but a narrow sample, not a statistically meaningful false-alarm rate with
a confidence interval (see `docs/LIMITATIONS.md`). It demonstrates the
recorder doesn't cry wolf on ordinary activity; it is not a claim about
rate across diverse real-world usage.

Generated 2026-10-26, same day as every other frozen artifact in this
repo — see `PROVENANCE.md`.
