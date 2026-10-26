# What's new (built during this hackathon)

Everything below was written between 2026-10-26 (kickoff) and submission.
Nothing in this list existed before the event. This file exists to satisfy
the judging requirement that reviewers be able to identify exactly what the
team built during the hackathon.

- [x] Recorder core: append-only, hash-chained ledger (`src/witness/ledger.py`, `canon.py`)
- [x] Listeners: decoy credential marker service, digest-only sink, process-group watcher, filesystem watcher
- [x] Detectors: marker-read, outbound-post, reported-vs-recorded mismatch, protected-write, experimental drift signal (stub)
- [x] Actions: stop process group, close decoy marker, Ed25519-signed receipt
- [x] Bundle format + schema-validated, whitelist-enforced `bundle.jsonl` export
- [x] Analyst pass (offline deterministic template; live model call deferred, no API key required)
- [x] Scenario arena: frozen-rule-set variant generation (private) + scoring (flagged/missed/false-alarm/time-to-stop), honest about a genuine miss
- [x] Console: bundle viewer, timeline, claim-diff, receipt verification (client-side, real Ed25519), drift panel
- [x] Recorded demo bundle used for every headline number in the console; corpus of additional benign/scenario bundles pending

Status checkboxes are updated as each item lands; see `git log` for the
commit that closed each one.
