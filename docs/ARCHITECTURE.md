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
               protected_write, drift[stub])  sign receipt — Ed25519)
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

## What's actually implemented (see `NEW.md` for the full checklist)

- **Ledger** (`ledger.py`, `canon.py`) — append-only, hash-chained. Each
  record's digest covers its own canonical JSON plus the previous record's
  digest. `verify_chain()` walks the whole chain and fails closed on any
  break.
- **Listeners** (`listeners/`) — a decoy-key marker service and a digest-only
  POST sink, both loopback-only; a process-group watcher (`psutil`); a
  filesystem watcher (`watchdog`, with a polling fallback if the OS watch
  limit is hit).
- **Detectors** (`detectors/`) — five independent checks: a decoy key being
  read, a POST reaching the decoy sink, a reported-vs-recorded mismatch (the
  agent's own claims vs. what the watchers actually saw), a write to a
  path marked protected, and a drift/behavioral-shape signal that is
  deliberately a stub returning no finding — it isn't scored or shown as a
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
