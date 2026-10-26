# What's new (built during this hackathon)

Everything below was written between 2026-10-26 (kickoff) and submission.
Nothing in this list existed before the event. This file exists to satisfy
the judging requirement that reviewers be able to identify exactly what the
team built during the hackathon.

- [ ] Recorder core: append-only, hash-chained ledger (`src/witness/ledger.py`, `canon.py`)
- [ ] Listeners: decoy credential marker service, digest-only sink, process-group watcher, filesystem watcher
- [ ] Detectors: marker-read, outbound-post, reported-vs-recorded mismatch, protected-write, experimental drift signal
- [ ] Actions: stop process group, close decoy marker, Ed25519-signed receipt
- [ ] Bundle format + schema-validated, whitelist-enforced `bundle.jsonl` export
- [ ] Analyst pass: read-only LLM report generation over a bundle (digests/enums only — no prompt/response text)
- [ ] Scenario arena: frozen-rule-set variant generation + scoring (flagged/missed/false-alarm/time-to-stop)
- [ ] Console: bundle viewer, timeline, claim-diff, receipt verification (client-side), drift panel
- [ ] Recorded benign + demo bundles used for every headline number in the README/video

Status checkboxes are updated as each item lands; see `git log` for the
commit that closed each one.
