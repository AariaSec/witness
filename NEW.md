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
- [x] Real Muse Code integration: `session.jsonl` envelope/flat-record parser (`src/witness/muse_journal.py`), a validated native plugin declaring all 5 observer hooks (`muse-plugin/`), a real tool-call mapping (`write_file` → `ClaimTool.write`), and a `witness record-muse` command — all proven against **a genuine Muse Code agent catching and saving a real decoy credential, and a genuine `mismatch` between its own self-report and what it actually touched**, independently detected end-to-end (`runs/frozen/muse-real-agent-proof-20261027-011548-7dca/`) — see `docs/NUMBERS.md` for the full story
- [x] **A second, architecturally distinct agent — Claude Code**: `claude_journal.py` parses its real session-log format, `ClaudeCodeClaimParser` + `witness record-claude`, built with **zero changes to the recorder core** (verified by `git diff --stat` on the recorder files — empty) — proof the architecture is general infrastructure, not a one-agent integration
- [x] **A second real-agent flagship catch, against Claude Code this time**: the exact same decoy-credential task given to a genuine, human-run `claude` session — independently caught saving the literal decoy value to `result.json` while its own final message claimed it hadn't used the value for anything (`runs/frozen/claude-real-agent-proof-20261027-012001-c976/`) — see `docs/NUMBERS.md` for the full story
- [x] **Receipt v0.2 + the merge gate**: the signed receipt is now bound to a git tree digest with per-file coverage, `witness verify` gates on policy (stop-severity findings) and `--against-tree` coverage (covered/modified/unattested), and a real GitHub Action (`witness-verify`) runs on real pull requests — **two live demo PRs, verified on actual GitHub-hosted runners, not simulated**: [PR #1, green](https://github.com/AariaSec/witness/pull/1) (a faithful session) and [PR #2, red](https://github.com/AariaSec/witness/pull/2) (the decoy-credential exfiltration catch)
- [x] **A real `pgroup_escape` detector**, closing a gap this project previously disclosed as undetected — fed by both `ProcWatcher`'s poll loop and a synchronous peer-pgid check at the marker/sink listeners (needed because the escapes actually demonstrated are too short-lived for polling alone). Proven on the originally-disclosed scenario (now a regression test) AND a freshly-authored, structurally distinct two-hop holdout never used to build the detector — see `docs/NUMBERS.md`

Status checkboxes are updated as each item lands; see `git log` for the
commit that closed each one.
