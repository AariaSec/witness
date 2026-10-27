# Limitations

Written honestly, on purpose — see `THREAT_MODEL.md` for what this is and
isn't trying to do. This file exists so a reviewer doesn't have to guess
what's solid versus what's a placeholder.

## Known, by design

- **Drift/behavioral-shape detector is a stub.** `detectors/drift.py`
  always returns no finding. It is not scored, not shown in the console as
  a working signal, and not part of any claimed detection rate. If it ever
  becomes real, it only gets promoted to a headline number after a
  train/holdout split and a pre-registered threshold — not before.
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

- **Only `Write` has ever been observed, end to end.** `Read`, `Edit`,
  `Bash`, `Grep`, `Glob` all appear as tool NAMES in this session's own
  tool listing, but none has a captured `tool_use`/`tool_result` pair.
  `_TOOL_RESULT_TYPE_TO_CLAIM_TOOL` holds exactly one entry (`"create"` →
  `ClaimTool.write`). A second, narrower gap: even for `Write`, only the
  `"create"` (new-file) `toolUseResult.type` has been observed —
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
