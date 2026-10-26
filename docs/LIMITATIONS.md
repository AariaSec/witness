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
