# NUMBERS

Every headline number anywhere in this project's README, deck, or demo
script traces to a `run_id` (or a `scores.json` built from a list of
`run_id`s) that a reader can go look up. This file is the index: number ->
where it came from -> how to reproduce it. If a number here has no
`run_id` next to it, treat it as not yet real.

Nothing is frozen here yet. This file starts with the one policy that
governs everything added to it later, plus the arena's current status.

## Policy: how a number gets into this file

1. The run (or arena batch of runs) that produced it must exist under
   `runs/frozen/` (single runs) or as a `scores.json` + its per-variant
   bundles (arena batches) — not described from memory, not re-derived
   after the fact.
2. The number is written next to the exact `run_id`(s) it came from. For
   an arena aggregate (detection rate, false-alarm rate, median
   time-to-stop), that means the `scores.json` path plus every `run_id`
   in its `per_run` list — not just the aggregate.
3. Updating a frozen run's numbers means re-recording, never hand-editing
   `scores.json` or a bundle. See `docs/ARCHITECTURE.md` §3.5 on bundle
   schema versioning: frozen runs are never migrated in place.

## G-Arena status

The arena harness (`witness.arena.runner.run_variants`,
`witness.arena.score.score`, `witness arena run` / `witness arena score`)
is implemented and tested — see `tests/unit/test_score.py` (synthetic
scoring logic) and `tests/integration/test_arena.py` (full pipeline over
`tests/fixtures/arena_variants/`, four local fixtures requiring no access
to anything private).

**The frozen rule set that generates arena variants lives in the private
companion repo, `witness-private` — named here by name only, never by
content.** Its `generator/seeds.yaml` is a frozen, hand-authored archetype
list (10 archetypes as of 2026-10-26: 2 benign/true-negative, 5 clean
malicious true-positives, 2 combined/ordering variants, and 1 archetype —
`escape_simple` — that is a deliberate, disclosed genuine miss: this
codebase has no detector for `FindingKind.pgroup_escape` yet, see
`docs/LIMITATIONS.md`). `witness-private/generator/gen_variants.py`
materializes that seed set into variant directories matching this repo's
`witness.arena.runner` contract and is never made public — see that
repo's `README.md` for why (a patent-counsel novelty review, independent
of this codebase).

A validation run of the full 10-archetype frozen seed set against this
build (2026-10-26, ad hoc — not committed as `runs/frozen/`, not a
headline number) produced exactly the mix the seed set's hand-written
`expected.json` files predicted: 8/10 malicious archetypes flagged
(detection_rate 1.0 against this seed set), 2/2 benign archetypes scored
true-negative (false_alarm_rate 0.0), median time-to-stop 8ms, and exactly
one genuine miss — `escape_simple`, `pgroup_escape` — reported honestly as
both `flagged` (its marker_read/outbound_post findings fired) and
`missed` (pgroup_escape did not), simultaneously, per `scores.json`'s own
per-run detail. This is cited here as evidence the pipeline is real and
correctly honest, not as a frozen number: freezing an official arena
`run_id` set under `runs/frozen/arena-<date>/` is a separate, later
decision (see the numbers-freeze date in the project plan), to be done
once there, with every `run_id` listed.

## Live analyst proof (real Meta open-weight model call)

The analyst pass (`witness.analyst.run.analyze`) defaults to the offline
deterministic template — zero API key, zero network call, by design (see
that module's docstring). It also supports an opt-in live `LLMClient`;
`BasetenClient` (`witness.analyst.client`) is a real adapter to Meta's
open-weight **Muse Spark Open** model (`meta-models/muse-spark-open-1026`)
via Baseten's OpenAI-compatible endpoint.

**Frozen proof run:** `runs/frozen/analyst-live-proof-20261026-145221-6150/`
(`bundle.jsonl` + `ledger.jsonl` from a real `witness demo --scenario
exfil` recording, plus `live_report.json`, the actual response from a real
call to `meta-models/muse-spark-open-1026`, 2026-10-26). Verified by hand
(not in the automated gate — see below for why): `analyst_status="ok"`,
schema-valid on the first attempt, `confidence=0.91`, correctly cited
`marker_read` and `outbound_post` findings with their exact evidence
`seq`s, wall time ~10-15s. This is the evidence that the project
genuinely, meaningfully uses a Meta open-weight model — not just a wired
code path that was never actually run.

**Why this isn't in the automated test suite:** a live network call has no
place in a gate that must stay green with zero API key (see
`ARCHITECTURE.md`/`LIMITATIONS.md`). The automated tests
(`tests/unit/test_analyst.py`) cover the exact same code path —
`analyze()`'s live branch, the retry-on-schema-failure logic, and the
fall-back-to-offline-on-any-failure guarantee — against a deterministic
fake `LLMClient`, so the *logic* is gate-verified even though the *real*
API call is only verified by this frozen, timestamped artifact.
