# Threat model

## What this is, in one sentence

`witness` detects a *disagreement* between what a coding agent reports doing
and what independently observed telemetry shows it did. It is not an
intrusion-prevention system, and it does not try to stop a sufficiently
capable or motivated adversary — see "What this does not claim" below.

## In scope

- An agent's own self-report (session log / JSON tool-call output) silently
  diverging from its actual file, process, or network activity — whether
  from a bug, a dropped step, or a genuinely unexpected action.
- A process reading a decoy credential placed in the working directory and
  sending it (or data derived from it) to a destination outside the
  recorder's own loopback sink.
- A write landing on a path the operator has marked protected, even if the
  agent's own report never mentions it.
- A spawned process escaping its original process group (e.g. via `setsid`)
  in a way that would otherwise let it survive a stop action.

## Out of scope — deliberately

- **Detecting a sufficiently careful adversarial agent.** Everything here is
  recorded from outside the agent's process, but an agent that never
  touches the decoy credential, never writes to a watched path, and never
  opens a network connection the sink can see leaves no signal for this
  design to catch. This is a detection/accountability layer, not a
  containment boundary.
- **Preventing the first bad action.** `witness` can stop a process group
  after a finding fires (and the protected-write case does this in single
  digits of milliseconds), but it cannot un-send a network request that
  already left the sink's visibility, and it cannot undo a file write that
  happened before the detector evaluated it. It shortens the window; it
  does not close it to zero.
- **Reading or judging prompt/response content.** By design, no detector or
  record ever sees the text of what the agent was asked or what it said.
  An attack contained entirely within reasoning the recorder never observes
  (no file write, no network call, no process spawn) is invisible here on
  principle, not by oversight.
- **The drift/behavioral-shape detector.** Present in the codebase as a
  stub that always returns no finding. It is not scored, not shown as a
  headline number, and not claimed as working — see `LIMITATIONS.md`.

## Why "decoy", never "real"

Every credential the detectors watch for is a decoy: generated fresh per
run, served through the marker service, and meaningless outside that run.
Nothing in this project ever handles, stores, or watches for a real
secret. Any screenshot or video that shows a "key" is showing a decoy value
and says so.

## Assumptions this design leans on

1. The hook mechanism the recorder attaches to runs outside the agent's own
   sandbox/approval system — confirmed directly from the hosting tool's own
   documentation (quoted in `ARCHITECTURE.md`), not assumed.
2. The operating system's file-watch and process APIs are trustworthy
   (i.e. this does not defend against a kernel-level or watcher-blinding
   compromise of the host itself).
3. The signing key used for receipts is generated and held locally
   (`~/.witness/keys/`, 0600) — a receipt proves the record it signs hasn't
   been altered since signing, not that the machine itself wasn't
   compromised before the recorder started.
