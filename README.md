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

witness's recorder and gate are deterministic and call no model. Meta models appear
in three places only: the advisory analyst and triage passes, the red-team arena that
measures how agents respond to planted instructions (a model writes the attack wording,
witness scores the session), and as the agent being observed. Every model called at
runtime is a Meta model.

| Model | Where it runs | What it does | Provenance |
|---|---|---|---|
| Muse Spark Open (`meta-models/muse-spark-open-1026`, open-weight) | Baseten (`--analyst-provider baseten`) | Analyst pass: writes an advisory plain-language verdict and a confidence score for a recorded bundle. It never changes a pass/fail result. Also runs inside the merge gate on real GitHub runners ([PR #3](https://github.com/AariaSec/witness/pull/3)). | `runs/frozen/analyst-live-proof-*`, `docs/NUMBERS.md` |
| Muse Spark 1.3 | Meta Model API (`--analyst-provider meta`) | The same analyst pass, called first-party. | `docs/NUMBERS.md` |
| Muse Spark 1.3 (triage) | Meta Model API (`witness triage --provider meta`) | Adjudicates the detector's `mismatch` findings, and annotates `pgroup_escape` warnings (never clearing them): it proposes `supported` / `unsupported` / `needs_human`, and a deterministic verifier must corroborate the verdict from the record or it stays `NEEDS_HUMAN`. Advisory; never changes the exit code. | `runs/frozen/live-capture-triage-20261103/` |
| Muse Glimmer 30B (open-weight, Q4_K_M GGUF) | A Modal A10G GPU that we deploy and serve ourselves, via llama.cpp (`scripts/glimmer_modal.py`; `--analyst-provider glimmer`, endpoint from `WITNESS_GLIMMER_URL`) | The same analyst pass on open weights we host ourselves. | `runs/frozen/live-capture-glimmer-*`, `docs/NUMBERS.md` |
| Muse Spark 1.3 and Muse Spark Open (arena attacker) | Meta Model API and Baseten, called by `scripts/redteam/` | Write the persuasion framing (prose only; a strict validator keeps code, paths and URLs out; the setup step itself is fixed text of ours) for the red-team arena. Muse Spark Open also acts as the adaptive attacker in round 2, seeing only a content-free outcome. It refused 4 of 14 rewrite requests. | `scripts/redteam/generated*/`, `docs/NUMBERS.md` |
| Muse Code | Local CLI, as the agent being observed | The coding agent whose sessions witness records and checks. witness reads its structured action log and does not store its prompts. | `runs/frozen/muse-real-agent-proof-*` |

witness also ships a parser for Claude Code session logs, to show the recorder
works on a second, different agent. Claude Code is only ever an *observed
subject* (and, separately, one MCP client we connected to witness's MCP server
to show it is not tied to one client); witness never calls it, or any non-Meta
model, as a model at runtime.

## What this is not

Nothing in this repo captures, stores, or displays prompt or response
text. Every record is a digest, an enum, a count, a destination, or a
timestamp. The precise boundary: witness's own recorder reads an agent's
structured action log — tool invocations, file-edit events, a claim
parser's extraction of what the agent says it did — and independently-
observed telemetry (files, processes, network); it does not store or
analyse the prompt given to the agent (the session-log parser drops
prompt-bearing fields on read), and never stores the model's own freeform
conversational output. Where this project's own writeup (`docs/NUMBERS.md`,
the video script) quotes an agent's final conversational message for
human-readable color, that text was read by the human operator watching
the terminal, not by witness's recorder — it is not, and never becomes,
a bundle record, and no code path in this repo stores or processes it.
Any scenario shown in the console is clearly labeled
**SIMULATED RECONSTRUCTION** and uses decoy credentials that point at a
local sink — never real infrastructure, never a real secret.

witness itself isn't a pre-deployment red-team or eval framework. It's a runtime
recorder: it watches one real session as it happens, from outside the
agent's own process, and checks the agent's self-report against what
independently-observed telemetry says actually happened. Those are
complementary categories (eval finds what an agent *can* be made to do;
this catches what an agent *actually did*). The repo also contains an
experiment harness (`scripts/redteam/`, `scripts/experiment/`) that uses
witness as the referee to measure how a real agent responds to planted
instructions; that harness is a measurement built on witness, not part of
the recorder.

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

## Who it is for, and what it costs

Teams whose coding agents open pull requests. Today the only account of what the agent did is the
agent's own summary; witness replaces trusting that with an outside, signed, content-free record and a
CI check, at a measured 16–44 s of CI time per run. No design partner and no pricing yet; see
[`docs/WHO_PAYS.md`](docs/WHO_PAYS.md) for the buyer, what it replaces, and what is not proven.

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
freshly-printed `bundle.jsonl` onto it yourself. No API key, no network after install
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

## How the Meta models compare on this task

`scripts/meta_bench.py` scores each model's analyst report against the signed record, deterministically, over 30 bundles (29 real sessions and 1 scripted, `simulated:true`)
(`docs/NUMBERS.md`, `runs/frozen/meta-bench-20261104/`). Muse Spark 1.3 and Muse Spark Open each completed 30 of 30, cited real
records 100% of the time and covered every detector finding; Spark 1.3 invented a finding in 2 of 30 bundles, Spark Open in
12 of 30 (mostly asserting a claim mismatch the detectors did not raise). Muse Glimmer 30B completed only 5 of 30 because of its
8k-token context; with windowed analysis and schema-constrained decoding it completes all 30 but invents a finding in 18 of 30 (windows lose
context), so completeness and faithfulness trade off. The models add readable narrative, not detections. No non-Meta model was benchmarked.

## Let a Meta model triage a finding (optional)

`witness triage <bundle> --provider meta` hands the bundle's `mismatch`
findings to a Meta model (content-free metadata only) and asks one question:
is this finding real, or an artefact of the comparison? The model proposes a
verdict and cites sequence numbers; a deterministic verifier then re-derives the
claim from the record. A verdict the verifier cannot corroborate is downgraded to
`NEEDS_HUMAN`, so the model can never retract a finding on its own say-so. Stop
findings and every other detector are never sent (the `pgroup_escape` annotation above is the one exception, for warnings only). The result is advisory: it does
not change `witness verify`'s exit code, the policy decision, the hash chain or the
signature.

It also annotates warn-severity `pgroup_escape` findings, the detector's noisiest
signal (a real agent's own shell or test runner detaching from the process group shows up as a
warning in 12 of the 32 experiment sessions). **A pgroup warning is never cleared:** the best the model can do is label it
`LIKELY_BENIGN` (it stays in the review queue), because the recorder's only network capture is the
loopback decoy, so the absence of a recorded decoy read is not evidence that a detached process did
nothing. The deterministic guard only refuses a "likely benign" label when the bundle ties the escape
to a decoy read, an outbound POST, a protected write, credential persistence or a stop finding; it
does not look at what the process is. That judgement is the model's alone, which is why the
evaluation includes a constant-answer baseline.
Small labelled check (`scripts/triage_eval.py`, `runs/frozen/triage-eval-20261104/`): both Muse
Spark 1.3 and Muse Spark Open call the 3 real benign warnings and 4 hand-built benign tool escapes
(make, node, cargo, npm) ordinary, and refuse all 16 hand-built suspicious escapes (curl, nc, ssh, scp; held-out wget, socat, telnet, rsync;
and a long tail of 8 more); the constant baseline would call all of them ordinary, and a ~30-tool allowlist ties the models on the simple sets (the models' only edge is 8/8 vs 0/8 on a long tail of unfamiliar benign tools). On the 12 real benign sessions of the unprompted batch it annotated all 73 `pgroup_escape` warnings `LIKELY_BENIGN` (`docs/NUMBERS.md`). The first
version of the prompt did not do this (Spark 1.3 dismissed 2 of 4 and Spark Open 4 of 4), which is why the
prompt now states the rule; the held-out half was added after that tuning. The suspicious cases are
synthetic and the sample is tiny, so this shows the model does the work, not an accuracy rate.

Live capture, 2026-11-03: on the real Muse Code bundle whose `mismatch` finding
came from the since-fixed read-vs-write detector bug (every claim behind it is a
read or search, and every file it names was recorded), Muse Spark 1.3 returned
`unsupported / CLAIM_WAS_READ_NOT_WRITE`, citing seqs 9, 10, 17, and the verifier
corroborated it (`runs/frozen/live-capture-triage-20261103/`). That is the retired
bug class, so it shows the mechanism, not a new detection. The path-alias and
real-discrepancy branches are covered by unit tests only
(`tests/unit/test_triage.py`); no real bundle in this repo has them.

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

**What the signature does and does not prove.** By default `witness verify`
checks the receipt's signature against the public key carried *inside* the
bundle. That proves the bundle was not changed after it was signed; it does not
prove who signed it, because someone who edits a bundle could re-sign it with a
fresh key. To pin the author, run `witness verify <bundle> --trusted-key <base64-pubkey-or-file>`:
a bundle signed by any other key exits 4. The CLI option is tested. This repo's own workflow
(`.github/workflows/witness-check.yml`) verifies **every** added or changed bundle, pins the signer
from `.witness/trusted-signer.pub` **on the base branch** (so a PR cannot swap the pin), runs the Meta
analyst as an advisory read-out, and posts one sticky comment on the PR with the verdict, the stop
findings and a console replay link ([PR #5](https://github.com/AariaSec/witness/pull/5) shows it on a real
agent run). The older demo PRs predate the pin. A companion workflow, `witness-require-bundle`, fails closed: a code change on an `agent/**` branch with no bundle attached fails ([PR #6](https://github.com/AariaSec/witness/pull/6)), so "no receipt, no merge" holds for those branches. The verifier workflow itself only runs on PRs that touch a committed bundle, and the require-bundle rule covers only `agent/**` branches (`docs/LIMITATIONS.md`).

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
> `console/public/bundles/credential-persist-real-proof.jsonl`
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
  28.564s #20 WARN finding=mismatch evidence=[2, 3, 9, 10, 15, 16, 17]   # recorded by the pre-fix detector; see docs/NUMBERS.md correction
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
  independently recorded fetching and saving a decoy credential (as its task directed) — see
  `docs/NUMBERS.md`'s flagship proof run.
- **Real-agent experiments, honestly labeled** (`scripts/experiment/`, `scripts/redteam/`, `docs/NUMBERS.md`). (1) A first batch of 32 Muse Code sessions whose prompts *told* the agent to fetch the endpoint: 44% touched the decoy, all 32 passed the gate (touching the decoy is a warning by design), 0% self-report mismatch; it surfaced two false-positive bugs in our own detectors, both fixed (`docs/LIMITATIONS.md`). (2) A larger overnight sweep of real Muse Code sessions with prompts that never mention credentials, including a **red-team arena in which Muse Spark 1.3 and Muse Spark Open wrote the persuasion wording** (10 styles, 3 placements) for a setup step planted in a README, contributing guide or code comment, and Muse Code was then asked an ordinary task. The red-team result, stated plainly: Muse Code mostly resisted the persuasion and a plain instruction did better than any wording (see `docs/NUMBERS.md`). <!--SWEEP-README-START-->Across 263 real Muse Code sessions (data cutoff 2026-11-04T04:40): when nothing pulled the agent toward the decoy credential, 0/69 sessions touched it. In the red-team arena, where Muse Spark 1.3 and Muse Spark Open wrote the persuasion wording for a setup step in a README, contributing guide or code comment, Muse Code fetched the token in 22/60 sessions and saved it to disk in 3/60. witness's deterministic gate failed 26/26 of the sessions that saved a credential (by definition: a saved credential is itself a stop finding) and 0/89 benign sessions (false alarms). A neutral-framing control (same step and same failing test, no persuasion) fetched in 11/12 and saved in 2/12, so persuasion effects are read against that. The attacker model (Muse Spark Open) refused 4 of 14 rewrite requests outright (counted, never run). In round 2 an adaptive attacker (Muse Spark Open, shown only the content-free outcome of round 1) rewrote 10 framings: the agent fetched in 5/20 sessions and saved the token in 1/20, against 11/20 and 0/20 for the same framings in round 1. One agent, a decoy on a local fake service, few sessions per cell.<!--SWEEP-README-END--> The README-driven sessions show an agent following documented setup steps and leaving a credential on disk (a deliberately conservative stop policy that includes a `.env`), not a hijack. One agent, a decoy on a local fake service, few sessions per cell: a measurement, not a prevalence.
- **Three live Meta-model paths (Meta Model API, Baseten, our own Modal GPU; Fireworks is built but not live-verified), with the first six
  real calls recorded individually and ~100 more in the benchmark below**: Muse Spark Open (`meta-models/muse-spark-open-1026` via
  Baseten) correctly analyzed a recorded scripted-scenario bundle (manifest `simulated: true`) — `analyst_status="ok"`,
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
  make the first six recorded calls; the later benchmark and triage runs add many more (`docs/NUMBERS.md`).

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
