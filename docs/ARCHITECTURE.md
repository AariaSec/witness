# Architecture

## The question this answers

A coding agent narrates its own actions as it works. `witness` asks whether
that narration matches what independently observed telemetry shows actually
happened on the machine — without ever reading the agent's prompts or
responses.

## Where the line sits

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI coding agent session                     │
│         (process under observation, spawned by witness)         │
└───────────────┬───────────────────────────────┬─────────────────┘
                 │ self-report                   │ real actions
                 ▼                               ▼
   ┌──────────────────────────┐      ┌────────────────────────────┐
   │ Agent's own session log  │      │  Independently observed:   │
   │ / JSON output             │      │  - files created/modified   │
   │ (tailed, never trusted)   │      │  - decoy-key reads/POSTs    │
   │                            │      │  - process spawns/exits     │
   └──────────────┬─────────────┘      └──────────────┬─────────────┘
                  │ assistant_claim records            │ fs_event / proc_event /
                  │                                     │ marker_read / outbound_post
                  ▼                                     ▼
          ┌───────────────────────────────────────────────────┐
          │        append-only, hash-chained ledger            │
          │   every record: seq, kind, ts_wall, ts_mono,       │
          │   prev digest, own digest — chain is tamper-evident │
          └──────────────────────────┬──────────────────────────┘
                                      │
                       ┌──────────────┴──────────────┐
                       ▼                             ▼
               detectors (marker_read,        actions (close decoy key,
               outbound_post, mismatch,       stop process group,
               protected_write, pgroup_escape, sign receipt — Ed25519)
               drift[stub])
                       │                             │
                       └──────────────┬──────────────┘
                                      ▼
                         bundle.jsonl (schema-validated,
                         allowed-keys whitelisted, chain re-verified)
                                      │
                                      ▼
                    console (client-side viewer, loads the bundle,
                    re-verifies the receipt signature in-browser,
                    derives every number with its backing seq refs)
```

## Why the recorder can see what the agent's own sandbox hides

Project hooks in the coding-agent tooling this targets run **outside** the
sandbox and approval system that govern the agent's own tool calls — this is
stated directly in the tooling's own documentation, not inferred. That's the
one architectural fact the whole design leans on: an observer positioned at
the hook layer sees real file/process/network activity regardless of what
the agent's sandbox permits or denies for the agent itself.

### How a hook actually gets installed (Muse Code) — corrected 2026-10-26

An earlier draft assumed hooks were declared in a plain file at
`<project-root>/.muse/hooks.json`. That's wrong, and the mistake is worth
naming so it doesn't resurface: hooks are not a standalone config file at
all. They are one capability family of a **native plugin bundle**,
confirmed against Meta's own bundled plugin-authoring reference
(`create-plugin/references/native-plugin-contract.md`, shipped with the
`muse` CLI) and empirically against the installed `muse plugins validate`
validator (muse 1.4.13, 2026-10-26):

- A plugin is a directory whose manifest lives at
  `<plugin-root>/.muse-plugin/plugin.json` (not a bare `hooks.json`, and
  not necessarily at the project root — the plugin root is wherever the
  bundle is created, e.g. this repo's `muse-plugin/`).
- The manifest's `capabilities.hooks` array holds entries shaped
  `{"id", "event", "command", "timeoutMs"?, "statusMessage"?}`, where
  `command` is structured argv (e.g. `["sh", "hooks/pre_tool_use.sh"]`),
  not a shell string.
- **Event-name casing is `PascalCase` in the manifest** (`SessionStart`,
  `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd`, …) — confirmed
  empirically, not guessed: `muse plugins validate` accepted
  `"event": "PreToolUse"` cleanly and rejected `"event": "preToolUse"`
  outright with `unsupported-hook-event`. This matters because the MSP
  wire schema's own `HookEventName` enum (exported via
  `muse schema generate-json-schema`) uses **lowerCamelCase**
  (`preToolUse`) for the same event vocabulary — that enum is the
  *catalog/listing* vocabulary (`HookCatalogEntry.event`, used when
  inspecting already-installed hooks), a different surface from the
  manifest's own declaration syntax. Don't assume the two ever have to
  match casing; they don't.
- A clean validation result is: process exits 0, stdout is parseable
  JSON, top-level `valid: true`, `diagnostics: []`. This repo's own
  plugin (`muse-plugin/`) validates clean with all 5 hooks above — see
  `docs/LIMITATIONS.md` for what validation does and doesn't prove.
- The hook subprocess's actual input contract (stdin? env vars? argv
  beyond the fixed command?) is **not documented anywhere found** in the
  bundled skill references or the exported MSP schema, and could not be
  determined empirically in this build either — `muse plugins hook test`
  (Meta's own fixture-driven test harness, which would have settled this)
  requires the plugin to be **installed** first, and every install path
  was blocked by a legitimate safety gate before a hook ever ran: `--scope
  user` is refused by this project's own tooling permission classifier
  ("Unauthorized Persistence" — it writes to global user config), and
  `--scope project` is independently refused by `muse` itself
  ("project-local plugin source is blocked because the workspace is
  untrusted"). Neither was worked around. This repo's hook scripts
  (`muse-plugin/hooks/*.sh`) are written defensively against this
  unknown — they drain and digest whatever bytes arrive on stdin within a
  bounded 0.5s window (discovered the hard way: a naive background `cat`
  silently reads from `/dev/null` instead of the real stdin unless the
  original fd is explicitly saved and re-pointed at first, since POSIX
  shells redirect a backgrounded job's stdin away from the parent's stdin
  by default) — but which channel Muse actually uses for a real
  invocation remains unverified. See `docs/LIMITATIONS.md`.

## Threat model — what's in scope and what isn't

Stated explicitly rather than left implicit, since "the recorder runs on
the same box as the agent, so what stops the agent from attacking the
recorder itself?" is the obvious next question a technical reviewer asks.

**In scope — things witness is built to catch:**
- An agent that omits, under-reports, or misdescribes an action in its
  own self-report (the `mismatch` detector's whole purpose).
- An agent that reads or exfiltrates a decoy credential (`marker_read`,
  `outbound_post`).
- An agent that writes to a path explicitly marked protected
  (`protected_write`).
- An agent (or something it spawns) that detaches from its own recorded
  process group to dodge the stop sweep (`pgroup_escape`).
- A receipt or bundle tampered with *after* the run ended (hash-chain
  recomputation, Ed25519 signature verification — both fail closed).

**Out of scope — not solved, not claimed to be:**
- **An agent with privilege equal to or above the recorder's own
  process.** If the agent (or whatever's driving it) has root, or can
  write to the recorder's own process memory, signing key, or ledger
  file, it can kill the watchers, forge records, or read the Ed25519
  private key before it ever signs anything. witness assumes the
  recorder runs with at least as much isolation as the agent it's
  watching — it is not a sandbox or a privilege boundary, it's an
  independent observer. A real deployment needs that isolation enforced
  by something else (a separate user, a separate container, a separate
  host) — witness doesn't provide it itself.
- **Live, in-flight ledger tampering.** `verify_chain()` catches tamper
  *after the fact*, on the file as it exists when read. It does not
  claim to detect an attacker rewriting the ledger file mid-run in a way
  that keeps the chain internally consistent (e.g., replacing the whole
  file with a forged-but-self-consistent chain before the real one is
  ever read) — that requires the signing key staying secret, which is
  the privilege-boundary assumption above, not a separate guarantee.
- **An agent that never touches the decoy, the marker, the sink, or any
  watched filesystem path, and simply lies about something with no
  independently-observable trace at all** (e.g., an internal reasoning
  claim with no corresponding external action). witness only catches a
  mismatch between what's *claimed* and what's *externally observable* —
  it was never designed to, and cannot, verify a claim with no
  observable footprint.

This list exists so "what does witness not do" is a design statement, not
a silent gap a judge or reviewer has to go find themselves.

## What's actually implemented (see `NEW.md` for the full checklist)

- **Ledger** (`ledger.py`, `canon.py`) — append-only, hash-chained. Each
  record's digest covers its own canonical JSON plus the previous record's
  digest. `verify_chain()` walks the whole chain and fails closed on any
  break.
- **Listeners** (`listeners/`) — a decoy-key marker service and a digest-only
  POST sink, both loopback-only; a process-group watcher (`psutil`); a
  filesystem watcher (`watchdog`, with a polling fallback if the OS watch
  limit is hit).
- **Detectors** (`detectors/`) — five independent checks, plus one planned:
  a decoy key being read, a POST reaching the decoy sink, a
  reported-vs-recorded mismatch (the agent's own claims vs. what the
  watchers actually saw), a write to a path marked protected, and a
  process detaching from the recorded process group (`pgroup_escape` —
  fed by both `ProcWatcher`'s poll loop and a synchronous peer-pgid check
  at the marker/sink listener, since the escaped processes seen in
  practice are often too short-lived for polling alone to catch). The
  sixth, a drift/behavioral-shape signal, is deliberately a stub
  returning no finding — it isn't scored or shown as a
  headline number until it's been validated against held-out data.
- **Actions** (`actions/`) — close the decoy key (serves 410 after), stop
  the process group (SIGTERM, 2s grace, SIGKILL, sweeping any pid seen at
  the marker/sink even if it escaped the original process group), and sign
  a receipt (Ed25519) over the run's final state.
- **Bundle export** (`bundle.py`) — the ledger becomes `bundle.jsonl` only
  after every record is checked against `schemas/allowed_keys.yaml` (a
  second, independent content-leak defence on top of pydantic's
  `extra="forbid"`) and the chain is re-verified. A violation refuses to
  emit (exit code 3, run marked quarantined) rather than silently shipping
  a bad bundle.
- **Console** (`console/`) — a static, client-side viewer. It re-verifies
  the Ed25519 receipt signature in the browser (not just trusting a
  "verified" flag from the recorder), and every derived number (time to
  detect, agreement rate) carries the record sequence numbers it was
  computed from.

## What a scenario proves, concretely

`witness demo` runs a small scripted assistant (`demo/sim_agent.py`) through
five scenarios — benign, exfiltrate-via-decoy, mismatch, protected-write,
process-group-escape — and each produces exactly the findings expected for
that scenario, with the protected-write case detected and stopped in single
digits of milliseconds against a 500ms budget (see `docs/NUMBERS.md` for the
measured figures and the run that backs each one).

## Recording a REAL Muse Code session instead of the stand-in

`witness record-muse <task> --lab <dir> --provider <provider> [--muse-arg
...]` is the real-agent path: it generates the Muse Code session id
itself (`--session-id <uuid>`), computes the real on-disk `session.jsonl`
path deterministically *before* spawning Muse (no directory-scanning
race — confirmed empirically), and tails that real file with
`MuseJournalClaimParser` instead of `sim_agent.py`'s simple format. The
OS-level watchers (files/processes/decoy marker+sink) are unchanged —
they don't care which coding agent is running.

This command never hardcodes `--disable-approval` or `--disable-sandbox`
itself — the operator supplies `--provider` and every `--muse-arg`
explicitly. `--provider echo` is always safe to smoke-test the plumbing
(zero tool execution, zero API key); `--provider meta` with `--muse-arg
--trust-workspace --muse-arg --disable-approval` is how a real,
tool-executing session is recorded, and was run successfully by the
project owner directly (see `docs/LIMITATIONS.md` for what that run did
and didn't prove).

## Claude Code integration: a second, architecturally distinct agent (added 2026-10-27)

`record-muse` proved the recorder works against one real coding-agent
format. A single integration risks looking like it was built TO that
format — so this adds a SECOND, independently-shaped one (Claude Code,
`claude` v2.1.310) to prove the actual architectural claim: **the
recorder core needed zero changes.** `src/witness/claude_journal.py` is
the only new source module; `cli.py` gained one additive command
(`record-claude`). Every pre-existing recorder-core file —
`ledger.py`, `canon.py`, `bus.py`, `listeners/*`, `detectors/*`,
`actions/*`, `bundle.py`, `models.py` — has an empty diff for this change
(verified with `git diff --stat` at commit time, not asserted). `tailer.py`
also needed no change: `ClaimParser` was already a pluggable protocol from
the Muse integration, and `Tailer._poll_file` already handled a parser
returning a list.

**The format itself is a genuinely different shape from Muse Code's,**
which is what makes this a real second data point and not just a
find-and-replace of the first:

- Muse's `session.jsonl` needs an envelope-unwrap step (`retained_frame` →
  `children[].record_json`, JSON-parsed a second time); Claude Code's
  session `.jsonl` is flat NDJSON throughout — one JSON object per line,
  always.
- Muse's tool-call evidence lives in a SINGLE record (`tool.result`'s
  `correlation_facts.tool_name` + `edit_facts.path`, or
  `tool_batch.effect.started`'s `record.tool_name` + `parallel_profile`).
  Claude Code splits the same information across TWO records — an
  `assistant` record's `tool_use` block (the request: tool name + intended
  args) and a later `user` record's `tool_result`/`toolUseResult` (the
  outcome). `claim_from_record` deliberately reads only the result side
  (see the module docstring for why — avoiding both a double-claim and a
  need for cross-record correlation state).
- Claude Code additionally has a THIRD outcome Muse's captured shapes
  never exercised: a tool call the operator's own permission gate
  refused outright (`toolDenialKind` + `is_error: true`, `toolUseResult`
  degrading from a structured dict to a plain error string). See
  `docs/LIMITATIONS.md` for the deliberate design decision on this path.

`witness record-claude --session-log <path> --lab <dir>` is the CLI
surface, and it is shaped differently from `record-muse` for a reason:
`record-muse` spawns the real agent itself, because Muse Code's `echo`
provider makes a zero-risk, zero-tool-execution smoke test possible.
Claude Code has no equivalent safe headless mode — running it
unsupervised would mean this codebase itself passing some form of
permission bypass, which is exactly the thing this project refuses to do
on an agent's behalf (same discipline as `record_muse` never hardcoding
`--disable-approval`). So `record-claude` never invokes `claude` at all:
the operator runs it themselves, by hand, in the same `--lab` directory,
and this command only tails the resulting session log. To keep
`_run_record`'s full orchestration (manifest, ledger, fs/marker/sink
watchers, signed receipt) working unmodified, it spawns a harmless
placeholder process (`sleep <N>`) to stand in for a process `ProcWatcher`
can watch. The one real cost: `proc_event` ground truth reflects this
placeholder, not the operator's actual `claude` process tree, so
`pgroup_escape`'s poll-based signal is blind in this mode — and its
synchronous marker/sink signal (`peer_escaped`) is deliberately disabled
here too (`bind_pgid_to_listeners=False`), since the placeholder's pgid
has no real relationship to the actual `claude` tree and would otherwise
misclassify every ordinary connection as an escape. Filesystem and decoy
marker/sink ground truth are otherwise unaffected (they watch `--lab` and
local ports, not a process tree). See `docs/LIMITATIONS.md`.

## Receipt v0.2 / CI gate: binding the receipt to a git tree (added 2026-10-27)

Everything above proves witness can faithfully record and sign what an
agent did. This section is the next step: turning that signed receipt
into something a CI pipeline can actually gate a pull request on — "the
merge gate for code no human fully reads," not just a forensic viewer
opened after the fact.

**Schema change, additive only.** `ReceiptBody` (`models.py`) gained four
OPTIONAL fields, every one defaulting to `None`/`{}`/`[]`:

- `git_commit_sha` — best-effort `git rev-parse HEAD` against the lab
  directory (`gittree.git_commit_sha`). `None` whenever the lab directory
  isn't a git repository at all — the common case, since most lab
  directories are disposable tmp dirs. Never required, never fails a run.
- `git_tree_digest` — sha256 of the canonical, sorted
  `[relative_path, file_sha256]` pair list for every regular file present
  under the lab directory at receipt-signing time (`.git/` excluded).
  This is a **snapshot**, not a strict pre/post-session diff: for a fresh
  per-session lab directory (the common case) that's equivalent to "every
  file the session touched"; for a lab directory reused across sessions
  (e.g. `record-claude` pointed at a real checkout the operator already
  had), pre-existing files are included too. Stated honestly rather than
  oversold — see `changed_file_digests` below for what this is actually
  useful for regardless.
- `changed_file_digests` — the `{relative_path: sha256}` map
  `git_tree_digest` is computed FROM, so a verifier can check a single
  file's coverage without recomputing the whole tree digest.
- `coverage` — which watchers (`fs`/`marker`/`sink`/`proc`) were genuinely
  active for this run. `record`/`record-muse`/`demo`/`arena` all get the
  full four; `record-claude` is the one caller that omits `proc` (its
  `ProcWatcher` watches a placeholder process, not the operator's real
  `claude` process tree — see that command's own docstring). This is the
  mechanism that makes "no finding" read as "not seen by active sensors,"
  never as "nothing happened."

**Why this didn't break every already-frozen receipt.** A receipt signed
before these fields existed never had these keys in its on-disk bytes.
Parsing it through the current schema fills them in with the defaults
above — which would silently change both the Ed25519 signature's input
and the hash-chain digest's input for every pre-v0.2 receipt, breaking
`witness verify` on everything under `runs/frozen/` and `corpus/benign/`
the moment this landed (caught during this change's own test pass, not
shipped and found later). The fix: `ReceiptBody.canonical_payload()`
(`models.py`) strips a v0.2 field from the dump whenever it's exactly at
its just-added default, before that dump is hashed or signed —
`strip_receipt_body_v02_defaults` is the single shared implementation
`actions/receipt.py` (the Ed25519 signature) and `ledger.py` (the
hash-chain digest) both call, so the two digest schemes can never
silently diverge on this. A receipt that genuinely sets any of these
fields keeps them in the hashed/signed payload — only the at-default case
reproduces the old, pre-v0.2 bytes.

**`witness verify`, substantially extended** (`cli.py`), fully backward
compatible with every existing bundle:

```
witness verify <bundle.jsonl> [--against-tree <dir>]
```

Still does the original chain + whitelist + signature re-verify first,
then adds two new checks, each independently gate-able:

1. **A small built-in policy check** — not a new rules engine, a verdict
   over findings the detectors already produced: FAIL if any `Finding`
   with `severity == "stop"` fired (e.g. the decoy-credential catch),
   PASS otherwise.
2. **`--against-tree <dir>`** — walks `<dir>` with the same per-file
   digest scheme, and classifies every file actually present there
   against the receipt's `changed_file_digests`: `covered` (digest
   matches), `modified` (path known, digest differs — edited after the
   session), or `unattested` (no covering receipt entry at all). A
   pre-v0.2 bundle has an empty `changed_file_digests`, so every file
   reads `unattested` against this check — an honest "this bundle never
   attested to a git tree," not a crash and not a silent pass.

Exit codes, each distinct and documented (never a silent pass): `0` OK,
`1` hash chain invalid, `2` posture fail (policy and/or tree check),
`3` leak-scan/whitelist violation, `4` receipt missing or signature
invalid. See `cli.py`'s `verify` command docstring for the authoritative
table.

**Adversarial coverage** (`tests/unit/test_cli_verify.py`): byte-flipped
signed body, wrong public key, a truncated chain, reordered records, a
missing receipt, a file modified after the session, and a file the
receipt never attested to — each produces its own distinct, non-zero
exit. The byte-flip and wrong-key cases specifically recompute the
record's own hash-chain digest after tampering (reusing `ledger.py`'s
internal `_record_digest`) so the test isolates "does the signature catch
this" from "does the chain catch this" — the hash chain alone, with no
external signing key, can never catch a self-consistent tamper; that's
exactly what the Ed25519 signature is for.

**GitHub Action** (`.github/actions/witness-verify/action.yml`) wraps
`witness verify` as a composite action: installs the package, runs
`witness verify` (optionally with `--against-tree`), and publishes the
same content-free stdout (counts, enums, digests, and relative paths —
never a prompt, a response, a file's contents, or a finding's underlying
evidence text) to the job's step summary and as action outputs
(`result`: pass/fail, `exit-code`). `.github/workflows/witness-check.yml`
wires it to `pull_request`, scoped narrowly to PRs that actually touch a
committed `runs/frozen/**/bundle.jsonl` — not every PR to this repo. This
repo had no `.github/workflows/` directory before this change; a human
should sanity-check the trigger condition before it's ever merged to
`main`.

**`--with-analyst`: a live Meta open-weight model call in the gate,
stated honestly as advisory.** `witness verify --with-analyst` also runs
the analyst pass (`witness.analyst.run.analyze`, §"Live analyst proof" —
a real call to Meta's open-weight **Muse Spark Open** via Baseten,
falling back to the offline deterministic template on any failure) and
prints its report (`status`, `confidence`, fixed summary codes — never
free text) alongside the existing checks. Said plainly, because it would
otherwise be an easy thing to oversell: **this call never affects
pass/fail.** The gate's exit code comes entirely from the chain/
signature/policy/tree checks above; the analyst's output is a narrative
annotation a human reviewer can read, not an input to the gate decision.
`BasetenClient`'s resolution order (`_resolve_analyst_client` in
`cli.py`) is `BASETEN_API_KEY` env var (how a CI runner supplies it, via
a GitHub Actions secret — composite actions can't read repo secrets
directly, so `witness-verify/action.yml` accepts it as an input and the
calling workflow passes `${{ secrets.BASETEN_API_KEY }}` through) →
local key file → `None` (the offline template), never raising either
way. Confirmed working end to end on a real GitHub-hosted runner, not
just locally — see `docs/NUMBERS.md`.
