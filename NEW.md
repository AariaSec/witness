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
- [x] Analyst pass: offline deterministic template (default, zero API key) + a real, verified live call to Meta's open-weight **Muse Spark Open** via Baseten (`meta-models/muse-spark-open-1026`) — see `docs/NUMBERS.md` for the frozen proof run
- [x] Scenario arena: frozen-rule-set variant generation (private) + scoring (flagged/missed/false-alarm/time-to-stop), honest about a genuine miss
- [x] Console: bundle viewer, timeline, claim-diff, receipt verification (client-side, real Ed25519), drift panel
- [x] Official frozen arena run (`runs/frozen/arena-20261026/`, 10 real run_ids) + a 5-run benign corpus (`corpus/benign/`) — see `docs/NUMBERS.md`
- [x] Real Muse Code integration surface: `session.jsonl` envelope/flat-record parser (`src/witness/muse_journal.py`), a validated native plugin declaring all 5 observer hooks (`muse-plugin/`, clean `muse plugins validate`), against three real local captures — see `docs/LIMITATIONS.md` for what's still genuinely unverified (the real tool-call payload shape; a live, tool-executing session is out of scope for this build's safety boundary)

Status checkboxes are updated as each item lands; see `git log` for the
commit that closed each one.
