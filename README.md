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
timestamp. The precise boundary: witness's own recorder reads an agent's
structured action log — tool invocations, file-edit events, a claim
parser's extraction of what the agent says it did — and independently-
observed telemetry (files, processes, network); it never reads the
prompt given to the agent, and never reads the model's own freeform
conversational output. Where this project's own writeup (`docs/NUMBERS.md`,
the video script) quotes an agent's final conversational message for
human-readable color, that text was read by the human operator watching
the terminal, not by witness's recorder — it is not, and never becomes,
a bundle record, and no code path in this repo stores or processes it.
Any scenario shown in the console is clearly labeled
**SIMULATED RECONSTRUCTION** and uses decoy credentials that point at a
local sink — never real infrastructure, never a real secret.

This also isn't a pre-deployment red-team or eval framework — it doesn't
attack an agent with adversarial prompts before it ships. It's a runtime
recorder: it watches one real session as it happens, from outside the
agent's own process, and checks the agent's self-report against what
independently-observed telemetry says actually happened. Those are
complementary categories (eval finds what an agent *can* be made to do;
this catches what an agent *actually did*), not competing ones.

## Why

Coding agents run with real file-system and network access. Today, the
only account of what an agent did is the agent's own self-report. This
project asks a narrower, falsifiable question: *if you record independently,
outside the agent's process, does the agent's self-report match reality —
and if it doesn't, can you catch it fast enough to act?*

This isn't hypothetical. On 2026-10-26 — the same day this project's
first commit landed — [the Washington Post reported](https://www.washingtonpost.com/technology/2026/10/26/researchers-cybersecurity-start-up-cathedral-got-inside-anthropic/)
that a security research team's AI agents reached internal business
systems at a frontier AI lab in under 12 hours, through third-party admin
software connected to it. Agents already operate with real production
access; this project doesn't claim it would have caught that specific
incident (different system, different scope) — it's cited only for why
an independent record of what an agent actually did, not just its own
self-report, matters now.

Framed as a control loop (see ["start with the sensor"](https://thenewstack.io/agentic-software-factory-sensor/)):
intent is the setpoint, the agent is the controller, and verification is
the sensor. A fast agent with a slow or low-fidelity sensor just retries
on stale information and ships what the sensor should have caught.
`witness` is that sensor, scoped to one question: does the agent's
self-report match an independent, content-free record of what actually
happened.

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

## Use it as a merge gate

A committed `bundle.jsonl` can gate a pull request, not just be viewed
after the fact — `witness verify` is a real CLI exit code (0/1/2/3/4, see
`docs/ARCHITECTURE.md`), and `.github/actions/witness-verify` wraps it as
a composite GitHub Action:

```yaml
- uses: AariaSec/witness/.github/actions/witness-verify@main
  with:
    bundle-path: runs/frozen/<run_id>/bundle.jsonl
    against-tree: .            # optional: flag files the receipt never attested to
    with-analyst: "true"       # optional: also run a live Meta Spark Open narrative (advisory only — never affects pass/fail)
    baseten-api-key: ${{ secrets.BASETEN_API_KEY }}
```

Two real, live pull requests on this repo show the gate actually running
on GitHub's own infrastructure, not simulated: [PR #1, green](https://github.com/AariaSec/witness/pull/1)
(a faithful session) and [PR #2, red](https://github.com/AariaSec/witness/pull/2)
(the decoy-credential catch) — both link straight into the live console
from their own CI step summary.

## Structure

- `src/witness/` — the recorder, listeners, detectors, ledger, bundler, CLI
- `console/` — the viewer (loads a `bundle.jsonl`, verifies its signature
  client-side, renders a timeline)
- `corpus/benign/` — recorded benign-run bundles (metadata only)
- `runs/frozen/` — the exact runs behind every number in this README
- `docs/` — architecture, threat model, numbers-with-provenance, demo script

## Real numbers, not claims

Every number below is a real, reproducible run — see `docs/NUMBERS.md` for
the exact `run_id`s and how to reproduce each one. Grouped by the three
properties a verification "sensor" is judged on (most teams only get two
of three — see the "Why" section above):

- **Latency** (time to signal): persistence detection fires in
  **5.9–19.3ms**, against a 500ms budget — measured on the owner's
  machine, not a CI runner; treat as provisional until re-measured there.
- **Fidelity** (escape rate): scenario arena, 10/10 archetypes recorded
  and scored — 8 flagged, 2 true-negative, 0 false alarms, **1 disclosed
  genuine miss at the time that frozen run was recorded** (2026-10-26:
  `pgroup_escape` had no dedicated detector yet). That frozen run is never
  edited in place, so it still shows the historical miss — but the gap
  itself was closed the next day: a real `pgroup_escape` detector now
  exists, with a regression test on the original miss and a passing
  result on a freshly-authored holdout (`escape_relay`) never used to
  build the detector — see `docs/NUMBERS.md`. The miss was reported, not
  hidden, and then fixed — an honest fidelity number, not a cherry-picked
  one.
- **Batch reproducibility** (relabeled from "bandwidth" after a `muse
  exec` adversarial-judge pass called out the original label as a
  category error — this is a serial batch score, not a measured
  concurrency/throughput result): 10 scenarios scored in one arena run
  today; the architecture (frozen seed set generated *before* any run,
  held in a private companion repo so nothing can be tuned against it)
  follows the same principle
  [StrongDM uses in production](https://thenewstack.io/agentic-software-factory-sensor/)
  — an external holdout set an agent can't optimize against.
- **A real coding agent, not a stand-in**: a genuine Muse Code session
  independently caught fetching and saving a decoy credential — see
  `docs/NUMBERS.md`'s flagship proof run.
- **Live Meta open-weight model proof**: a real call to Muse Spark Open
  (`meta-models/muse-spark-open-1026` via Baseten) correctly analyzed a
  real bundle — `analyst_status="ok"`, `confidence=0.91`. A second,
  independent hosting provider for the same model (Fireworks,
  `witness verify --with-analyst --analyst-provider fireworks`) is built
  and unit-tested, proving the analyst role isn't tied to one third-party
  host — see `docs/LIMITATIONS.md` for its live-verification status.

## Founder disclosure

The founder of this project runs a company in AI-agent security
(AariaSec). Same problem domain, no shared code — verify it yourself in
one command:

```
git log --reverse --format='%ad %h %s' --date=iso
```

Every commit falls inside the hackathon window (first: 2026-10-26
kickoff). Full detail, including the hash-manifest check against that
company's private source tree, in `PROVENANCE.md`.

## Licence

MIT — see `LICENSE`.
