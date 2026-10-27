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

- **`pgroup_escape` has no dedicated detector**, only an action-level
  fallback: the stop action sweeps any pid seen at the marker/sink even if
  the process watcher never saw it spawn. This covers the demonstrated
  escape scenario but is not the same as a first-class finding with its
  own evidence trail.
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

## Muse Code integration (added 2026-10-26)

What's real as of this pass, all against a genuine, locally installed
`muse` (Meta's coding-agent CLI, v1.4.13) — never a live, tool-executing
session (see the safety boundary this work operated under):

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
