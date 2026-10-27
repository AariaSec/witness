# Demo script

**Status: locked shot list, timed.** Consolidated from the four-model
Round-4 planning pass (`~/Desktop/AariaSec/meta-hackathon/ROUND4-FINAL-
PLAN.html`), updated to reflect what actually shipped (the `pgroup_escape`
miss this plan originally expected to just *disclose* got fixed during
the build — see below). Target runtime: 2:50–3:00. Every number/claim
below traces to a file or URL in this repo — nothing here is aspirational.

**Required opening line (hackathon rule, not optional):**

> Everything in this repository was built this week, starting at the
> October 26th kickoff. The founder also runs an existing AI-agent-
> security company, AariaSec — no code, schema, or prompt from that
> product is in this repo. Full commit history is public.

---

## 0:00–0:15 — Hook

**Visual:** cold open, no logo. A real agent's session on screen — its
own calm, confident final message: *"It looks like a decoy credential,
not a real token. I didn't use it for anything."*

**Voiceover:**
> This is a real AI coding agent. It just saved a credential to a file
> on disk — and told me it didn't.

**Caption (muted-viewer support):** "Real agent. Real session. Not staged."

---

## 0:15–0:35 — The problem, and why now

**Visual:** split screen — agent's narration on one side, a blank
question mark on the other labeled "what actually happened?"

**Voiceover:**
> Every coding agent writes its own report of what it did. That report
> is the only account anyone checks — and it's produced by the exact
> same process that did the work. On October 26th — the same day we
> started building this — the Washington Post reported that a security
> research team's AI agents reached internal systems at a frontier AI
> lab in under 12 hours, through third-party software connected to it,
> not by breaking the model. AI agents are fast. The question is: when
> one does something you didn't expect, how fast do you find out — and
> from who?

**Caption:** "The agent's report is the only witness to itself. Until now."

*Source for the factual claim:
[Washington Post, 2026-10-26](https://www.washingtonpost.com/technology/2026/10/26/researchers-cybersecurity-start-up-cathedral-got-inside-anthropic/).
Keep factual and sourced — no implying witness would have caught that
specific incident (it wouldn't have; different system, different scope).
Framing for "why this matters now," not a claim about this project's
reach.*

---

## 0:35–1:05 — Flagship proof (Muse Code)

**Visual:** the live console (`aariasec.github.io/witness/`), loaded with
the corrected Muse Code flagship bundle
(`?bundle=bundles/muse-real-agent-proof.jsonl`). Walk the timeline: the
agent fetches a decoy webhook endpoint, the independent marker service
catches the read, the agent's own claim log never names the two files it
touched.

**Voiceover:**
> witness is an independent recorder. It never reads the agent's prompts
> or reasoning — only files, processes, and network, from outside the
> agent's own process. Here, a genuine Muse Code session — real hosted
> model, real API key — fetched a decoy credential and saved the literal
> value to disk. Its own claim log never mentioned either file. witness
> caught the mismatch independently, with its own evidence trail.

**On-screen number:** "marker_read + mismatch — both independently caught"
(traces to `runs/frozen/muse-real-agent-proof-20261027-011548-7dca/`)

---

## 1:05–1:30 — Tamper test

**Visual:** the console's "Tamper test" button — flip one byte of the
signed receipt, watch the Ed25519 signature verification flip from valid
to invalid, live, in the browser, no login, no backend.

**Voiceover:**
> Every run ends in a signed, hash-chained receipt. Flip one byte, and
> the signature fails — right here, in your browser. Nothing to trust
> but math.

**Caption:** "Ed25519, verified client-side. @noble/ed25519."

---

## 1:30–2:00 — Generalization (Claude Code)

**Visual:** quick cut to the Claude Code flagship run
(`?bundle=bundles/claude-real-agent-proof.jsonl`) — same task, same
catch, different agent. Show the `git diff --stat` proving zero changes
to the recorder core.

**Voiceover:**
> A recorder that only works for one agent is a feature of that agent,
> not independent verification. So we proved it on a second, completely
> different agent — Claude Code — with zero changes to the recorder
> core. Same task, same catch: it fetched the same decoy credential,
> saved it, and told me it hadn't used it.

**Caption:** "Zero recorder-core diff — verified by `git diff --stat`, not asserted."

*(Optional, cut first if time is short: one sentence noting this submission's own tooling used Claude Code — disclosed in the README, not dwelt on here.)*

---

## 2:00–2:30 — The merge gate

**Visual:** a real, live GitHub pull request —
[PR #2](https://github.com/AariaSec/witness/pull/2) — red X, the
Actions log showing the content-free step summary (`policy: FAIL (stop
findings: 1)`). Cut to [PR #1](https://github.com/AariaSec/witness/pull/1),
green check, same gate, a faithful session.

**Voiceover:**
> This isn't just a viewer. The signed receipt is bound to the actual
> git tree, and a real GitHub Action runs `witness verify` on every pull
> request. A tampered or missing receipt — or a stop-severity finding —
> fails the check, visibly, before a merge ever happens. And that gate
> is itself partly powered by a live call to Meta's open-weight Muse
> Spark Open model, scoring what it sees.

**On-screen:** the two PR URLs, side by side, green and red.

---

## 2:30–2:50 — Honesty: a real miss, found and fixed

**Visual:** `docs/LIMITATIONS.md`'s `pgroup_escape` entry — show the
"before" (disclosed gap) and "after" (the fix, dated, with a fresh
holdout scenario — `escape_relay` — proving it generalizes, not just
patches the one case it was built against).

**Voiceover:**
> This project publishes its own misses. Partway through this week we
> found a real gap — a process that detaches from its own group went
> undetected. We disclosed it, then fixed it, then proved the fix on a
> scenario we wrote *after* the fix existed — so passing it couldn't be
> explained by just matching the one case we already knew about.

**Caption:** "Disclosed. Fixed. Proven on a case the fix never saw."

---

## 2:50–3:00 — Close

**Visual:** repo URL + live console URL, side by side.

**Voiceover:**
> Every coding agent writes its own report. witness is the second
> witness — for any agent, on every commit.

**On-screen:**
`github.com/AariaSec/witness` · `aariasec.github.io/witness`

---

## Cut order if time runs short

1. The Claude-Code self-reference aside (if kept at all) — cut first.
2. Collapse "Honesty" beat to one sentence in voiceover over the merge-gate
   shot, rather than its own 20s block.
3. Never cut: the receipt + `witness verify` + one real green/red PR
   check, the Claude Code parser with at least one genuine human-run
   session, RULE-1-analog compliance, honest non-cherry-picked scoring,
   and Muse Code keeping the majority of screen time.

## Capture checklist (do these in order, before editing)

- [ ] Re-confirm both console deep links load clean on the LIVE deployed
      URL (not localhost) — `?bundle=bundles/muse-real-agent-proof.jsonl`
      and `?bundle=bundles/claude-real-agent-proof.jsonl`.
- [ ] Screen-record the tamper-test flip in real time (don't fake the
      transition — it has to actually compute).
- [ ] Screen-record PR #1 and PR #2's Actions tab live, scrolled to the
      step summary.
- [ ] Record the `git diff --stat` command showing the empty recorder-core
      diff, in a real terminal, not a screenshot.
- [ ] Voiceover recorded separately, synced in edit — not live narration
      over screen capture (gives room to hit exact timings per beat).
