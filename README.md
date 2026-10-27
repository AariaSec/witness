# witness

An independent recorder for AI coding-agent sessions. It compares what an
agent *reports it did* against an out-of-process, content-free record of
what actually happened on the machine — file writes, outbound connections,
process spawns — captured by a recorder that sits outside the agent's own
sandbox.

> **Built entirely during the Meta Global AI Developer Hackathon**
> (Oct 26 – Nov 4, 2026). Every file, commit, and line of code in this
> repository was written during the event. See `NEW.md` for the exact
> claim list and `PROVENANCE.md` for commit-level proof. No code from any
> pre-existing product is included here.

**Live console, no login, no API key required:
[aariasec.github.io/witness](https://aariasec.github.io/witness/)**
— loads with a real recorded bundle pre-loaded.

## What this is not

Nothing in this repo captures, stores, or displays prompt or response
text. Every record is a digest, an enum, a count, a destination, or a
timestamp. Any scenario shown in the console is clearly labeled
**SIMULATED RECONSTRUCTION** and uses decoy credentials that point at a
local sink — never real infrastructure, never a real secret.

## Why

Coding agents run with real file-system and network access. Today, the
only account of what an agent did is the agent's own self-report. This
project asks a narrower, falsifiable question: *if you record independently,
outside the agent's process, does the agent's self-report match reality —
and if it doesn't, can you catch it fast enough to act?*

## Quickstart

```
pip install -e .
witness keygen
witness demo
```

Records a real scripted session end-to-end and prints the resulting
`bundle.jsonl` path. To view it:

```
cd console && npm install && npm run dev
```

then drag that `bundle.jsonl` onto the page (or use the file picker, or
pass `?bundle=<path>`). No API key required for any of this — the console
also ships with its own bundled demo bundle pre-loaded on first open.

## Structure

- `src/witness/` — the recorder, listeners, detectors, ledger, bundler, CLI
- `console/` — the viewer (loads a `bundle.jsonl`, verifies its signature
  client-side, renders a timeline)
- `corpus/benign/` — recorded benign-run bundles (metadata only)
- `runs/frozen/` — the exact runs behind every number in this README
- `docs/` — architecture, threat model, numbers-with-provenance, demo script

## Real numbers, not claims

Every number below is a real, reproducible run — see `docs/NUMBERS.md` for
the exact `run_id`s and how to reproduce each one.

- **Persistence detection**: 5.9–19.3ms from write to stop, against a
  500ms budget.
- **Scenario arena**: 10/10 archetypes recorded and scored, 8 flagged,
  2 true-negative, 0 false alarms, **1 disclosed genuine miss**
  (`pgroup_escape` has no dedicated detector yet — see
  `docs/LIMITATIONS.md`).
- **Benign corpus**: 5 independent runs, zero false alarms.
- **Live Meta open-weight model proof**: a real call to Muse Spark Open
  (`meta-models/muse-spark-open-1026` via Baseten) correctly analyzed a
  real bundle — `analyst_status="ok"`, `confidence=0.91`.

## Founder disclosure

The founder of this project runs a company in AI-agent security
(AariaSec). This repository is a clean, from-scratch build started at
hackathon kickoff — see `PROVENANCE.md` for the commit history that
proves it. No code, schema, or prompt from that company's product is
included here.

## Licence

MIT — see `LICENSE`.
