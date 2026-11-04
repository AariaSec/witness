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

## What existed before vs. what was built this week

| | What | In this repo? |
|---|---|---|
| **Existing before the event** | [AariaSec](https://aariasec.com), the founder's separate company and product (runtime AI-agent monitoring). Not part of this submission and not judged. | No. Same problem domain, no shared code (see `PROVENANCE.md`). |
| **Built this week** | `witness`: the recorder, detectors, signed receipts, merge gate, MCP server, console and analyst pass. The full itemised list is in `NEW.md`. | Yes, all of it. First commit 2026-10-26. |
| **Private, declared** | A private companion repo holds only the frozen seed set for the scenario arena, so nothing can be tuned against it. | No. Nothing here needs it: the arena results are recorded in `runs/frozen/`, and every other feature runs from this repo alone. |

## Meta models: which, where they run, what they do

witness's recorder and gate are deterministic and call no model. Models appear
in two places only, and every model called at runtime is a Meta model.

| Model | Where it runs | What it does | Provenance |
|---|---|---|---|
| Muse Spark Open (`meta-models/muse-spark-open-1026`, open-weight) | Baseten (`--analyst-provider baseten`) | Analyst pass: writes an advisory plain-language verdict and a confidence score for a recorded bundle. It never changes a pass/fail result. Also runs inside the merge gate on real GitHub runners ([PR #3](https://github.com/AariaSec/witness/pull/3)). | `runs/frozen/analyst-live-proof-*`, `docs/NUMBERS.md` |
| Muse Spark 1.3 | Meta Model API (`--analyst-provider meta`) | The same analyst pass, called first-party. | `docs/NUMBERS.md` |
| Muse Glimmer 30B (open-weight, Q4_K_M GGUF) | A Modal A10G GPU that we deploy and serve ourselves, via llama.cpp (`scripts/glimmer_modal.py`; `--analyst-provider glimmer`, endpoint from `WITNESS_GLIMMER_URL`) | The same analyst pass on open weights we host ourselves. | `runs/frozen/live-capture-glimmer-*`, `docs/NUMBERS.md` |
| Muse Code | Local CLI, as the agent being observed | The coding agent whose sessions witness records and checks. witness reads its structured action log, never its prompts. | `runs/frozen/muse-real-agent-proof-*` |

witness also ships a parser for Claude Code session logs, to show the recorder
works on a second, different agent. Claude Code is only ever an *observed
subject*; witness never calls it, or any non-Meta model, at runtime.

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

This isn't hypothetical. In July 2026, OpenAI models under test escaped their
sandbox and compromised Hugging Face's systems
([OpenAI's account, 2026-08-26](https://openai.com/index/hugging-face-incident-and-the-road-ahead/)).
In an independent investigation, METR found that agents also spoofed tool calls
in their own transcripts, so what the transcript said they ran was not what
ran (about 7% of the transcripts METR reviewed; METR describes these as
small-scale tests aimed at fooling the benchmark's scorer). OpenAI's own
post-mortem notes that the monitoring that would have flagged the early
activity was not running on those evaluations. That is the gap an independent,
out-of-process record is for. This project doesn't claim it would have caught
that incident (different system, different scope); it targets the same class
of problem: an agent's self-report diverging from what actually happened.

A second example: on 2026-10-26, the same day this project's
first commit landed, [the Washington Post reported](https://www.washingtonpost.com/technology/2026/10/26/researchers-cybersecurity-start-up-cathedral-got-inside-anthropic/)
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

**One command, one real session, end to end:**

```
./scripts/judge_quickstart.sh
```

Creates a venv if needed, generates a signing key, records a real
`sim_agent` session (decoy key read → decoy value exfiltrated), runs
`witness verify` (the actual merge-gate check, real exit code — `2` means
a real stop-severity finding fired), and opens the already-hosted
[live console](https://aariasec.github.io/witness/) so you can drag the
freshly-printed `bundle.jsonl` onto it yourself. No API key, no network
except the recorder's own loopback marker/sink, nothing uploaded (parsed
client-side in your own tab). Measured on the owner's machine: 1.6s with
an existing `.venv`, 12.1s from a completely fresh clone (includes
`pip install -e .`) — verified by
`tests/integration/test_judge_quickstart.py`, which runs this exact
script, not a reimplementation of it.

Or by hand:

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

## Run the live analyst (optional, needs your own key)

Nothing above needs a key. The analyst pass adds a plain-language report from
a Meta model; it is advisory only and never changes a verdict or exit code.
To run it yourself, supply your own key — judges and reviewers do not need
ours, and no key is ever committed to this repo.

```
cp .env.example .env          # then edit .env and fill in ONE key
set -a; source .env; set +a   # the CLI reads the shell environment, not .env
witness verify <bundle.jsonl> --with-analyst --analyst-provider meta
```

| `--analyst-provider` | Environment variable | Model |
|---|---|---|
| `meta` | `META_API_KEY` | Muse Spark 1.3 via the Meta Model API |
| `baseten` | `BASETEN_API_KEY` | Muse Spark Open (open-weight) |
| `fireworks` | `FIREWORKS_API_KEY` | same open-weight model, second host (built and unit-tested, **not live-verified**) |
| `glimmer` | `WITNESS_GLIMMER_URL` (no key) | Muse Glimmer 30B on a Modal GPU we deploy ourselves |

A live call is not instant: in our frozen captures the Meta Model API took 24 s and Glimmer on Modal took 58 s (plus a ~70 s cold start), and some attempts timed out (54-142 s) and fell back to the offline template (`analyst_status="offline"`). The fallback is by design and the verdict never depends on the call.

With no key set the command still succeeds and prints the offline template
(`analyst_status="offline"`). The recorded runs in `runs/frozen/` include the
analyst output from our own live calls, so you can inspect real model output
without running anything.

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

Live pull requests on this repo show the gate running on GitHub's own
infrastructure (the CI runs are real): [PR #1, green](https://github.com/AariaSec/witness/pull/1)
(a faithful session); [PR #2, red](https://github.com/AariaSec/witness/pull/2)
(a decoy-credential exfiltration, where the recorded session is a scripted
stand-in agent and the console labels it **SIMULATED**); and
[PR #4, red](https://github.com/AariaSec/witness/pull/4) (a real
`credential_persist` catch from a real agent session). Each links straight
into the live console from its CI step summary.

## Use it from a coding agent (MCP)

`witness verify`'s logic — plus the advisory analyst narrative — is
exposed as four read-only MCP tools (`witness_verify_bundle`,
`witness_list_findings`, `witness_check_tree_coverage`,
`witness_analyze_bundle`) over a local stdio server — ask any MCP client
to check a receipt in plain conversation instead of running the CLI by
hand. Deliberately NOT a hosted connector: no auth, no public
distribution, no platform review — install the `mcp` extra and point an
agent's `mcpServers` config at it:

```bash
pip install -e ".[mcp]"
```

```json
{
  "mcpServers": {
    "witness": {
      "transport": "stdio",
      "command": "/absolute/path/to/witness/.venv/bin/witness-mcp-server",
      "args": []
    }
  }
}
```

**Live demo:** with that configured, ask Muse Code directly —

> "Use the witness tool to check whether
> `runs/frozen/credential-persist-real-proof-20261027-135303-9dba/bundle.jsonl`
> passes its merge gate, and list any findings."

— and it calls `witness_verify_bundle` + `witness_list_findings` itself,
getting back the real, signed, chain-verified result (`policy: FAIL`,
the real `credential_persist` finding) rather than anything it could
make up. Verified end-to-end: `tests/integration/test_mcp_server_protocol.py`
spawns the real server and talks to it over real stdio JSON-RPC via the
official MCP client SDK — the same path any real MCP client uses.

Not a one-client trick: the same server is also registered and connected
to **Claude Code** (`claude mcp add witness -- /path/to/.venv/bin/witness-mcp-server`,
`claude mcp get witness` → `Status: ✔ Connected`) — a genuinely different
MCP client from Muse Code, proving this is a real protocol implementation
rather than something tuned to one client's quirks. The fourth tool,
`witness_analyze_bundle`, wraps the exact same `analyze()` used by
`witness verify --with-analyst` — `provider="offline"` (default) needs no
key at all; `provider="baseten"` or `provider="meta"` runs a live model
call, falling back to the offline template on any failure, same
retry/fallback guarantee as the CLI.

## Use it from a terminal

A third surface, alongside the browser console and the MCP server: a
live or replayed feed of a session's records, for a human operator
watching in their own terminal.

```
witness watch runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl --speed 50
```

```
   0.002s #0 manifest run=20261027-011548-7dca
   ...
  15.940s #12 marker_read pid=27210
  15.940s #13 WARN finding=marker_read evidence=[12]
  28.564s #20 WARN finding=mismatch evidence=[2, 3, 9, 10, 15, 16, 17]
  28.630s #21 receipt signed key=Flnpc3We8Q… stop=not_needed
```

`bundle.jsonl` (or `--replay`) replays at real recorded pacing, sped up
by `--speed`; a bare `ledger.jsonl` from an in-progress `witness record`
run is tailed live, ending when the signed receipt appears — verified
against a real in-progress recording, not just a finished bundle: a real
`credential_persist` session's two `STOP` findings and their `stop_pgroup`
actions streamed live, in order, as the file was being written. Same
content-free rule as every other surface (`src/witness/watch.py`'s
`line_for` renders only existing digest/enum/count/path fields) — see
`tests/unit/test_watch.py` and `tests/integration/test_watch_cli.py`.

## Structure

- `src/witness/` — the recorder, listeners, detectors, ledger, bundler, CLI
- `console/` — the viewer (loads a `bundle.jsonl`, verifies its signature
  client-side, renders a timeline)
- `corpus/benign/` — recorded benign-run bundles (metadata only)
- `runs/frozen/` — the exact runs behind every number in this README
- `docs/` — architecture, threat model, numbers-with-provenance, demo script
  (start with `docs/CAPABILITY_MAP.md` for the one-table claim/evidence/
  boundary summary of everything below)

## Real numbers, not claims

Every number below is a real, reproducible run — see `docs/NUMBERS.md` for
the exact `run_id`s and how to reproduce each one. Grouped by the three
properties a verification "sensor" is judged on (most teams only get two
of three — see the "Why" section above):

- **Latency** (time to stop): across the 8 stop-expected runs in the latest
  frozen arena (`runs/frozen/arena-20261028b/scores.json`), the process
  group was stopped in **3–16 ms (median 9 ms)**, against a 500 ms budget —
  measured on the owner's machine, not a CI runner; treat as provisional
  until re-measured there.
- **Fidelity** (escape rate): the latest frozen arena run
  (`runs/frozen/arena-20261028b/`) scored 11 scenarios — 9 flagged, 0 missed,
  0 false alarms, 2 benign. The first official run (2026-10-26): scenario arena, 10/10 archetypes recorded
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
  concurrency/throughput result): 10 scenarios scored in one arena run (11 in the latest run)
  today; the architecture (frozen seed set generated *before* any run,
  held in a private companion repo so nothing can be tuned against it)
  follows the same principle
  [StrongDM uses in production](https://thenewstack.io/agentic-software-factory-sensor/)
  — an external holdout set an agent can't optimize against.
- **A real coding agent, not a stand-in**: a genuine Muse Code session
  independently caught fetching and saving a decoy credential — see
  `docs/NUMBERS.md`'s flagship proof run.
- **A small, honestly labeled experiment** (`scripts/experiment/`, n=16 decoy-adjacent / n=16 control real Muse Code sessions): **44% touched the decoy**, controls **100% clean**, and a **0% self-report mismatch rate** — a real, slightly deflating finding: these agents did not misreport in this sample. It also surfaced two false-positive bugs in our own detectors, both fixed (`docs/LIMITATIONS.md`).
- **Three independent live Meta model providers, six real calls on
  record**: Muse Spark Open (`meta-models/muse-spark-open-1026` via
  Baseten) correctly analyzed a real bundle — `analyst_status="ok"`,
  `confidence=0.88` on first run (2026-10-26), re-run clean under the
  later canonical-code-enum schema fix at `confidence=0.93` — and, as a
  second, first-party proof, a direct call to **Meta's own hosted Model
  API** (`witness verify --with-analyst --analyst-provider meta`,
  `muse-spark-1.3`, no third-party host) worked on the first attempt
  against a different real bundle — `analyst_status="ok"`,
  `confidence=0.6` originally, `0.85` on the same later re-run. Together
  they cover both halves of "meaningfully use Meta Model API and/or Meta
  open-weight models." Two further live captures on 2026-11-03 (Muse Spark
  1.3 at `confidence=0.9`, Muse Glimmer 30B on a Modal GPU we deploy
  ourselves at `confidence=0.85`; frozen under `runs/frozen/live-capture-*`)
  make six real calls in all — see `docs/NUMBERS.md`.

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
