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
- **Analyst report is offline-only in this build.** `analyst/run.py`
  produces a deterministic template report from bundle counts; no live
  model call is wired in. This is deliberate: the hackathon's Meta API
  credit is only valid for a 10-day window, and the judge-facing product
  must never depend on a live API call that could fail once that window
  closes.
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
- Wiring the live Meta Model API analyst path once a key is available,
  with the offline template kept as the permanent fallback rather than
  retired.
