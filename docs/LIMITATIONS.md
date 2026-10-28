# Limitations

Written honestly, on purpose — see `THREAT_MODEL.md` for what this is and
isn't trying to do. This file exists so a reviewer doesn't have to guess
what's solid versus what's a placeholder.

## Known, by design

- **Drift/behavioral-shape detector — closed 2026-10-27, `info`-severity
  only, not a headline number.** `detectors/drift.py` now scores real
  session shape against a frozen, pre-registered baseline (median/MAD
  modified z-score, threshold 3.5). Real train/holdout discipline: a
  first baseline (5 synthetic + 2 real sessions) turned out to mostly
  detect "real agent vs. scripted session," not benign vs. malicious —
  found by validating against real held-out data, not assumed to work.
  Fixed by recording 8 more real sessions (`corpus/benign-real/`) and
  rebuilding the baseline from 10 real sessions only. Re-validated: zero
  false alarms on four real held-out sessions, including two genuinely
  malicious ones (expected — drift measures timing/shape, a different
  signal from the content-specific detectors, not a replacement for
  them). Still disclosed as small-n (n=10) and experimental — `POLICY`
  attaches no action to it, so it can never block a merge, and it is not
  counted in any detection-rate claim in this file or `docs/NUMBERS.md`.
  Full writeup: `detectors/drift.py`'s module docstring and
  `docs/NUMBERS.md`'s drift-detector section.
- **Analyst report defaults to offline, on purpose — not because a live
  path doesn't exist.** `analyst/run.py` always falls back to a
  deterministic template report from bundle counts if no live client is
  given, or if a live call fails/times out/fails schema twice. A real live
  path IS wired (`BasetenClient`, Meta's open-weight Muse Spark Open) and
  independently verified against a real bundle — see `docs/NUMBERS.md` —
  but the offline template remains the default and the only path the
  judge-facing demo depends on, since the hackathon's Meta API credit
  window and any third-party credit pool can both run dry or rate-limit
  before judging.
- **Single-machine, single-run scope.** There is no fleet view, no
  cross-run aggregation beyond the arena scoring (if shipped — see
  `NUMBERS.md`), and no persistence of findings beyond one bundle.

## Known gaps worth naming

- **The console's receipt verification didn't match what the backend
  actually signed, for every Receipt v0.2 bundle** (fixed 2026-10-27,
  found while capturing video clips, not by inspection). `ReceiptBody.
  canonical_payload()` strips a v0.2 field before signing when it's
  exactly at its just-added default — `git_commit_sha` is null for every
  run so far, since no lab directory is a real git repo — so pre-v0.2
  bundles stay byte-identical. The console's own canonicalisation
  (`verifyReceipt.ts`) never mirrored that stripping: it included
  `"git_commit_sha":null` (genuinely present in the raw JSON) in its
  canonical form, a byte-level divergence from what was actually signed.
  Concretely: **both flagship real-agent bundles showed "RECEIPT
  INVALID" in the live, deployed full console** — the share view never
  hit this, since it doesn't render `ReceiptPanel` at all, which is why
  it went unnoticed until someone opened the full console specifically.
  Fixed with `stripV02FromNode`/`stripV02FromPlain` mirroring the
  backend exactly, plus a permanent regression test
  (`console/tests/receiptV02Interop.test.ts`) against both real
  bundles — the existing interop test only ever covered a pre-v0.2
  bundle, which is exactly the class of gap that let this ship.
- **`pgroup_escape` now has a dedicated detector** (fixed 2026-10-27,
  `src/witness/detectors/pgroup_escape.py`) — this entry used to say it
  had none; left here, corrected, rather than deleted, for the same
  reason the historical `runs/frozen/arena-20261026/escape_simple` bundle
  is kept unmigrated: the gap was real and disclosed, and the fix is more
  credible shown against that history than if it looked like there was
  never a gap. Two independent signals feed it: `ProcWatcher`'s poll loop
  (reliable only if the escaped process outlives one poll interval) and
  `MarkerRead`/`OutboundPost.peer_escaped`, resolved synchronously by the
  marker/sink listeners at the moment they discover the connecting peer
  (not subject to the poll race — this is the one that actually matters,
  since the demonstrated scenarios' escaped processes are short-lived).
  Proven on two things, not one: the originally-disclosed `escape`
  scenario (now a regression test, `tests/integration/test_arena.py`) and
  a freshly-authored, structurally distinct two-hop holdout,
  `escape_relay` (`src/witness/demo/sim_agent.py`), frozen at
  `runs/frozen/pgroup-escape-fresh-holdout-20261027-020507-c256/` —
  written after the detector existed specifically so passing it couldn't
  be explained by overfitting to the one case it was built against. See
  `docs/NUMBERS.md`.
- **`pgroup_escape` severity is split by corroboration, not just
  detection** (fixed 2026-10-27, same day as the detector itself): bare
  detachment (`ProcWatcher`'s poll signal alone) is `warn`, not `stop` —
  found via the experiment harness (`scripts/experiment/`), not
  inspection: a real, unmodified Muse Code binary legitimately spawns
  internal subprocess workers that detach into their own session for
  ordinary reasons, and treating that alone as `stop` (which also drove a
  destructive `stop_pgroup` action — now gated on severity too, see
  `actions/__init__.py`) fired on roughly a third of real, harmless
  sessions in one batch. Only detachment corroborated by also touching
  the decoy (`MarkerRead`/`OutboundPost.peer_escaped`) stays `stop`. The
  two already-proven scenarios (`escape`, `escape_relay`) are unaffected
  — in both, the detached process is also the one that touches the
  decoy, so corroboration was already present.
- **`mismatch` no longer compares `read` claims against write-only
  recorded events** (fixed 2026-10-27, found the same way as the
  `pgroup_escape` false positive — by actually running the experiment
  harness, not by inspection). The detector used to union EVERY claimed
  path, regardless of `ClaimTool`, into one set compared against
  create/modify `FsEvent`s. A `read` claim's path legitimately never
  appears there — reads leave no fs trace, by design (the console's own
  `ClaimDiff` already has an explicit "not observable" status for exactly
  this). This fired on roughly a quarter of real, harmless control-task
  sessions in the same batch, every single one explained by the agent
  reading a pre-existing seed file it never created or modified.
  `_PATH_WRITING_TOOLS = {write, edit}` now gates which claims contribute
  to the comparison; `read`/`search`/`shell`/`http`/`other` claims never
  did (and still don't) assert "I wrote this path," so excluding them
  from a write-vs-write comparison is a correction, not a loosening.
- **The `escape`/`escape_relay` integration tests are occasionally flaky**
  — observed 1 failure in 5 full runs. Both spawn real subprocesses and
  depend on `ProcWatcher`'s poll timing and real OS scheduling under
  load; this is consistent with the detector's own disclosed timing
  sensitivity (see above), not a new issue. Not chased further yet —
  worth a retry-once wrapper if it proves disruptive to CI.
- **Chain verification checks links, not full recomputation**, in the
  console specifically: the browser-side viewer checks that each record's
  `prev` points at the previous record's `digest`; it trusts the recorder's
  own digest computation rather than recomputing every hash client-side.
  The backend's own `verify_chain()` does recompute.
- **The "said vs. did" matching rule** (which claim corresponds to which
  recorded event) is a reasonable heuristic — a shell claim is matched to
  the nearest process spawn within a short time window — not a formally
  specified algorithm. It's good enough to drive the demo honestly, not
  good enough to call a proof.

## Muse Code integration (added 2026-10-26, closed the same day)

What's real against a genuine, locally installed `muse` (Meta's
coding-agent CLI, v1.4.13) — **including, as of later the same day, a
real, tool-executing `--provider meta` session, end to end**
(`witness record-muse`, `runs/frozen/muse-real-agent-proof-20261026-185538-7c88/`
— a real agent fetched a decoy credential and saved it to a tracked
file, independently detected). The "never a live session" boundary below
describes this codebase's OWN subprocess calls (it still never passes
`--disable-approval`/`--disable-sandbox` itself — the project owner ran
that combination directly, by hand, exactly once this was needed):

- **`src/witness/muse_journal.py`** correctly unwraps a real
  `session.jsonl` file: the large majority of lines are already a flat
  inner MSP record; a minority (observed: the session-opening permission
  transaction) are a `retained_frame` envelope whose `children[].record_json`
  must be JSON-parsed a second time. Both shapes were confirmed against
  three independent real captures (one top-level session, two subagent
  sessions), not inferred from documentation alone.
- **A real, validated native plugin** (`muse-plugin/`) declares all 5
  requested hooks (`SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`,
  `SessionEnd`) and passes `muse plugins validate` cleanly (`valid: true`,
  `diagnostics: []`, every hook classified `"supported"`). See
  `docs/ARCHITECTURE.md` for the casing finding (manifest events are
  `PascalCase`, confirmed by the validator accepting `PreToolUse` and
  rejecting `preToolUse`).

### Partially closed 2026-10-26, later the same day

- **The real tool-call payload shape — one case confirmed, others still
  open.** Once a Meta API key was available, the project owner ran a
  real, tool-executing session directly (`muse exec --provider meta
  --trust-workspace --disable-approval`, outside this codebase's own
  safety boundary — this repo's own code never runs that combination
  itself). It produced a genuine `payload_type: "tool.result"` record
  with clean, enumerable fields: `payload.correlation_facts.tool_name`
  (`"write_file"`), `payload.correlation_facts.outcome` (`"success"`),
  and `payload.edit_facts.path`/`.added`. `muse_journal.py`'s
  `_TOOL_NAME_TO_CLAIM_TOOL` now maps exactly that one observed
  tool_name, `write_file` → `ClaimTool.write`, extracting the path and
  count — never `payload.text`, which is content-bearing and confirmed
  (not guessed) to carry it. See `tests/fixtures/muse_journal/
  real_tool_call_session.txt` (sanitized) and the tests built against it.
  **Still genuinely open:** only `write_file` has ever been observed — a
  shell command, a file read, or a web request were never exercised in
  this one capture, and `_TOOL_NAME_TO_CLAIM_TOOL` is not populated with
  a guess for any of them.
- **The hook subprocess's input contract** (stdin vs. env vars vs. argv).
  `muse plugins hook test` — Meta's own fixture-driven harness built
  specifically so this never needs a live session — requires the plugin
  to be installed first, and both install paths available in this
  environment were refused by a legitimate safety gate (this project's
  own permission classifier for `--scope user`; `muse`'s own
  workspace-trust gate for `--scope project`). Neither was worked around,
  per the same discipline as not working around the `--yolo` block. The
  hook scripts are written defensively (drain + digest whatever arrives
  on stdin within a bounded window, ignore argv/env content entirely) so
  they're safe regardless of which channel turns out to be real, but
  which channel that is remains unconfirmed. See `docs/ARCHITECTURE.md`.
- **`retained_frame.content_sha256`'s preimage.** Present on every
  envelope line observed, but several plausible reconstructions (sha256
  of the concatenated `record_json` strings; of the envelope object minus
  that field, sorted-key and as-is; of the `children` array; of
  re-serialized inner records) were tried empirically against a real
  captured value and none matched. `muse_journal.py` does not attempt to
  recompute or verify this field — it would rather be silent than claim a
  verification that isn't real.

## Claude Code integration (added 2026-10-27)

A second, architecturally distinct coding-agent integration — see
`docs/ARCHITECTURE.md` for why this one matters more as a proof point
than as a feature (zero recorder-core diff, a genuinely different wire
format, a new outcome shape Muse's captures never exercised).

What's real: two sanitized, committed fixtures
(`tests/fixtures/claude_journal/success_session.txt`,
`denied_session.txt`) from a genuine, isolated, throwaway scratch session
run with a real, locally installed `claude` (confirmed v2.1.310,
2026-10-26/27) — the same task (write `hello.txt`) run twice, once with
the `Write` tool granted and once denied. `src/witness/claude_journal.py`
correctly parses both: flat NDJSON (no envelope step needed, unlike Muse),
a confirmed success shape (`user` record's `toolUseResult.type ==
"create"` + `.filePath`), and a confirmed denial shape (`toolDenialKind` +
`is_error: true`, `toolUseResult` degrading to a plain string).

- **`Write` and `Bash` have been observed, end to end; `Read`, `Edit`,
  `Grep`, `Glob` have not.** (Updated 2026-10-27 — this found a real
  blind spot, not a planned extension: the Claude Code flagship session
  fetched and saved the decoy credential with a single Bash command,
  never calling `Write` at all, so the original Write-only mapping
  produced zero claims for that entire session — see `docs/NUMBERS.md`'s
  paired-comparison section.) Bash's confirmed success shape has no
  `type` key at all (unlike Write's `"create"`/`"update"`), just
  `{"stdout", "stderr", "interrupted", "isImage", "noOutputExpected"}` —
  mapped to a count-only `ClaimTool.shell` claim, no path or host
  extracted (the command itself is content-bearing text, never parsed).
  `Read`, `Edit`, `Grep`, `Glob` all appear as tool NAMES in this
  session's own tool listing, but none has a captured `tool_use`/
  `tool_result` pair yet. A second, narrower gap: even for `Write`, only
  the `"create"` (new-file) `toolUseResult.type` has been observed —
  `"update"` (overwriting an existing file) is a plausible but
  uncaptured shape and is deliberately not mapped. Extend only from
  another real, observed capture.
- **The denial path is a deliberate design decision, not an oversight —
  a denied tool call never produces an `AssistantClaim`.** Three
  alternatives were considered and rejected: (1) parsing the human-
  readable denial sentence to recover which tool/path was denied — prose
  parsing, refused on the same content-discipline grounds `muse_journal.py`
  refuses to recompute `content_sha256` from a guess; (2) correlating
  back to the paired `assistant` record's `tool_use` block by
  `tool_use_id` to recover the tool/path structurally — technically
  possible without touching prose, but adds state to what is otherwise a
  stateless, per-record parser for no benefit this project currently
  needs; (3) misusing an existing `TailMeta` event literal (e.g.
  `"parse_error"`) to signal "denied" — rejected as factually wrong, the
  line parses fine. The chosen answer is silence: `AssistantClaim` means
  "the assistant did (or asserts it did) X"; a refusal is specifically the
  absence of that, and the recorder's independent, OS-level `FsWatcher`
  ground truth already establishes whether a file was (or wasn't)
  written — a denial produces no ground-truth fs event either, so there
  is nothing for a missing claim to create a false mismatch against.
- **A real, committed-fixture content leak was found and fixed during
  this same pass.** The two fixtures were sanitized by replacing every
  `content`/`rendered`/`shape`/`params`/`originalFile`/`structuredPatch`/
  `message`/`input`/`text`/`prompt`-keyed string value — but the
  sanitization matched the exact key name `"prompt"` and missed the
  camelCase `lastPrompt` field (`type: "last-prompt"` records), which
  carried this capture's literal real task text
  (`"Create a file named hello.txt containing exactly the word hello"`)
  unredacted, 3 times in each fixture. Found by this module's own test
  suite (`test_success_fixture_contains_no_unredacted_prose`,
  `test_denied_fixture_contains_no_unredacted_prose` initially failing),
  fixed by replacing the literal leaked string with the same
  `PLACEHOLDER_CONTENT` token used elsewhere in both files, and the
  regression tests now assert the specific phrase is absent, not just a
  generic substring. A reminder that "already sanitized" fixtures still
  need independent verification, not trust.
- **`record-claude`'s process-tree blind spot.** Because this command
  never spawns `claude` itself (see `docs/ARCHITECTURE.md` for why), its
  `ProcWatcher` watches a harmless placeholder process, not the
  operator's real `claude` process tree. `proc_event` records (and
  `pgroup_escape` detection, which depends on them) do not reflect ground
  truth for the real agent in this mode — only the fs watcher and decoy
  marker/sink do. This is a deliberate, documented scope reduction
  forced by the "never invoke Claude Code with a bypass flag" constraint,
  not a silent gap.

## Modal-sandbox stop_pgroup: detection confirmed, containment not — disclosed, still open (2026-10-27)

Re-ran the flagship `credential_persist` task inside a real Modal cloud
sandbox (`scripts/modal_latency_proof.py`), using Modal credits granted
for this hackathon, specifically to replace the README's "measured on
the owner's machine, not a CI runner" latency caveat with a third-party
infrastructure result. The *detection* side held up perfectly: a real,
non-simulated session, chain-verified, receipt-signed,
`policy: FAIL (stop findings: 1)`, same as the local proof. The
*containment* side (`stop_pgroup`'s actual SIGTERM/SIGKILL) reported
`"failed"` every time, across three separate runs.

The investigation (not just accepting the first failure): the first run
reported `latency_ms=3009` against the then-default 2.0s grace + 1.0s
kill-wait (3.0s total) — read as "maybe just 9-80ms too tight," since a
later `proc_event` showed the agent's process exiting shortly after.
Widened to 3.0s/2.0s (5.0s total) and re-ran: still `"failed"`, this
time at 5023ms. Widened again to 5.0s/3.0s (8.0s total): still
`"failed"`, at 8024ms. **The overshoot stayed ~20-24ms (one poll-loop
tick) at every budget tried, not a growing or shrinking margin** — proof
the process group was never actually confirmed dead within any window,
however large. That rules out "needs more time" and points at something
structural: signal delivery to a process group most likely doesn't
behave the same way under Modal's sandboxed container runtime as it
does on a bare POSIX host (the process exits that looked like
confirmation were likely the container itself tearing down after the
Modal function returned, not our `SIGKILL` landing). The `stop_pgroup`
defaults were reverted to 2.0s/1.0s rather than widened further — see
`actions/stop_pgroup.py`'s docstring and
`tests/unit/test_actions.py::test_stop_pgroup_defaults_were_investigated_not_blindly_widened`.

**What this means, stated plainly:** `witness` recording and detection
are infrastructure-agnostic — they worked correctly on Modal's cloud
sandbox with no changes. The destructive containment action
(`stop_pgroup`) is not yet confirmed to work in every sandboxed/
virtualized deployment environment; it is confirmed to work on a real
POSIX host (macOS, the flagship proofs) and NOT yet confirmed on
Modal's sandbox specifically. This is disclosed, not hidden, and not
treated as fixed — the root cause (likely process-group signal
semantics under that sandbox's isolation layer) needs more investigation
than was available in the remaining time before submission.

## What would make this stronger, with more time

- A real arena run across many generated scenario variants, scored against
  a rule set frozen before generation (see `NUMBERS.md` for whether this
  shipped and what it found, including genuine misses).
- A corpus of recorded benign runs large enough to estimate a false-alarm
  rate with a real confidence interval, not just "zero false alarms in the
  demo set."
- The live analyst path currently does a single-shot call (full record set
  in context) rather than the originally-specified multi-turn
  `get_record`/`query` tool-calling loop — simpler, verified working, but
  a real tool-calling loop would scale better to very large bundles.
- Wiring the live **Meta Model API** (Muse Spark, hosted) path once that
  key is available — today's live path uses the open-weight model via
  Baseten, which already satisfies "meaningfully use Meta Model API
  and/or Meta open-weight models," but the hosted-API path specifically
  is still untested.
