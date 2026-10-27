# Demo script

**Status: locked shot list, timed.** Consolidated from the four-model
Round-4 planning pass (`~/Desktop/AariaSec/meta-hackathon/ROUND4-FINAL-
PLAN.html`), updated three times since: (1) the `pgroup_escape` miss this
plan originally expected to just *disclose* got fixed during the build;
(2) an external review pass (Fable) led to running a real 32-session
experiment — which itself found and fixed two more bugs, turned the
single flagship anecdote into an honest rate, and is now its own beat;
(3) a second 3-model review round (Opus/Sonnet/Haiku,
`~/Desktop/AariaSec/meta-hackathon/video-strategy/`) caught a real
structural flaw — the original hook opened on a Claude Code quote with
no checkable artifact, and the hook/flagship/generalization beats didn't
clearly attribute which agent said what. Rewritten: the hook now opens on
a fully chain-verified, judge-checkable finding instead; the Claude Code
quote survives only as explicitly-labeled color later, never as proof.
Target runtime: 3:00. Every number/claim below traces to a file or URL in
this repo — nothing here is aspirational. (4) Confirmed via the official
Cerebral Valley / Meta office-hours answer (2026-10-26): the hackathon
rule requiring disclosure of pre-existing work is real and the video
itself — not just the README — must open with it. Previously this was a
documentation-only note above the Hook with no allocated runtime; moved
into an actual 0:00–0:05 title-card beat so the video itself satisfies
the rule, and the Hook shortened from :20 to :15 to hold 3:00 total.

---

## 0:00–0:05 — Required disclosure (hackathon rule, not optional)

**Visual:** plain title card, no logo animation yet — text on screen,
read aloud in voiceover, before the cold open.

**On-screen text / voiceover:**
> Everything in this repository was built this week, starting at the
> October 26th kickoff. The founder also runs an existing AI-agent-
> security company, AariaSec — no code, schema, or prompt from that
> product is in this repo. Full commit history is public.

---

## 0:05–0:20 — Hook

**Revised after a 3-model review round surfaced a real structural risk:**
the original hook opened on a direct quote from Claude Code's final
message ("I didn't use it for anything"). That quote is real, but it has
no checkable artifact — by this project's own design, raw conversational
text is never stored in any bundle (the privacy rule this whole project
is built around). Opening a video about independent verification on the
one claim a judge *can't* independently verify is a real risk, not a
style note. Replaced with the strongest claim that IS fully verifiable:
Muse Code's own `mismatch` finding (`runs/frozen/muse-real-agent-proof-
20261027-011548-7dca/`, finding seq 20, evidence seqs 2/3/9/10/15/16/17)
— chain-linked, signed, and loadable by any judge, right now, at the
exact URL on screen.

**Visual:** cold open, no logo, straight into the live console
(`aariasec.github.io/witness/?bundle=bundles/muse-real-agent-proof.jsonl`),
already scrolled/zoomed to the "Agent said / Witness recorded" diff — the
"decoy key fetched" row in red, the two "never mentioned" file rows
beneath it.

**Voiceover:**
> This is a real AI coding agent's own report of what it did. It never
> mentions touching either of these two files. Both are independently
> recorded, right here — and you can check this yourself, right now, at
> this URL.

**Caption (muted-viewer support):** "Real session. Real finding. Chain-verified — check it yourself."

---

## 0:20–0:35 — The problem, and why now

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

## 0:35–1:05 — Flagship proof (Muse Code), zoomed out

**Visual:** same console, same bundle as the hook — now pull back to the
full timeline: the agent (Meta's own Muse Code, real hosted model, real
API key) fetching a decoy webhook endpoint, the independent marker
service catching the read, the file-write events, the signed receipt.

**Voiceover:**
> witness is an independent recorder. It never reads the agent's prompts
> or reasoning — only files, processes, and network, from outside the
> agent's own process. This is how it caught what you just saw: Muse
> Code fetched a decoy credential and saved the literal value to disk.
> Its claim log never mentioned either file. witness didn't need to read
> a word of its reasoning to catch that — only what actually happened on
> disk.

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
(`?bundle=bundles/claude-real-agent-proof.jsonl`) — same task, different
agent, same `marker_read` finding, chain-verified. Show the
`git diff --stat` proving zero changes to the recorder core (exact
command + commit range in `docs/NUMBERS.md` — reproducible against this
public repo, not a frozen artifact, since commit history is itself
immutable).

**Voiceover:**
> A recorder that only works for one agent is a feature of that agent,
> not independent verification. So we proved it on a second, completely
> different agent — Claude Code — with zero changes to the recorder
> core. Same task: it fetched the same decoy credential and saved it to
> disk — caught the same way, independently, no reasoning read.

**On-screen aside, clearly labeled as color, not a claim:** the agent's
own final message, watched live by the operator running the session —
*"I didn't use it for anything."* Caption underneath, small: *"Shown for
context — witness itself never stores this text; this is the operator's
own observation, not a bundle record."* This exists so the video itself
discloses the exact boundary a sharp judge would otherwise probe.

**Caption:** "Zero recorder-core diff — verified by `git diff --stat`, not asserted."

*(Optional, cut first if time is short: one sentence noting this submission's own tooling used Claude Code — disclosed in the README, not dwelt on here. If further compressed, cut the on-screen aside too — the marker_read finding + zero-diff claim alone fully carry this beat.)*

---

## 2:00–2:25 — The merge gate

**Visual:** a real, live GitHub pull request —
[PR #2](https://github.com/AariaSec/witness/pull/2) — red X, the
Actions log showing the content-free step summary (`policy: FAIL (stop
findings: 1)`). Cut to [PR #1](https://github.com/AariaSec/witness/pull/1),
green check, same gate, a faithful session.

**Voiceover:**
> This isn't just a viewer. The signed receipt is bound to the actual
> git tree, and a real GitHub Action runs `witness verify` on every pull
> request. A tampered or missing receipt — or a stop-severity finding —
> fails the check, visibly, before a merge ever happens. The pass/fail
> decision is fully deterministic — chain, signature, policy. It can
> optionally also show a live narrative from Meta's open-weight Muse
> Spark Open model alongside the verdict — advisory only, never the
> thing that decides pass or fail.

**On-screen:** the two PR URLs, side by side, green and red.

---

## 2:25–2:55 — Honesty: real numbers, and real misses, found and fixed

**Visual:** `docs/NUMBERS.md`'s experiment table on screen — the four
rates, the n=16/n=16 label visible. Cut to `docs/LIMITATIONS.md`'s
`pgroup_escape` entry — "before" (disclosed gap) and "after" (the fix,
dated, with a fresh holdout scenario, `escape_relay`, proving it
generalizes).

**Voiceover:**
> One catch is an anecdote. So we ran it 32 times — real Muse Code
> sessions, decoy-adjacent tasks and ordinary ones side by side. 44% of
> the time, the agent actually touched the decoy. And running this
> immediately found two real bugs in our own detectors — false alarms on
> completely ordinary sessions. We fixed both the same day, and this is
> the clean re-run: zero false alarms, not a cherry-picked one. This
> project publishes its own misses — found, disclosed, fixed, and proven
> on a case the fix never saw.

**Caption:** "32 real sessions. 2 bugs found by running it, not reading it. Both fixed."

---

## 2:55–3:00 — Close

**Visual:** repo URL + live console URL, side by side.

**Voiceover:**
> Every coding agent writes its own report. witness is the second
> witness — for any agent, on every commit.

**On-screen:**
`github.com/AariaSec/witness` · `aariasec.github.io/witness`

---

## Cut order if time runs short

1. The Claude Code "on-screen aside" quote (if kept at all) — cut first;
   the marker_read finding + zero-diff claim alone fully carry that beat.
2. Collapse the "Honesty" beat to the 44%/32-runs line only, dropping
   the pgroup_escape before/after visual — the number alone still carries
   the point.
3. Never cut: the receipt + `witness verify` + one real green/red PR
   check, the Claude Code parser with at least one genuine human-run
   session, RULE-1-analog compliance, the experiment's honest numbers
   (44% marker-touch, 0% mismatch, 2 bugs found and fixed), and Muse Code
   keeping the majority of screen time.

## Capture checklist (do these in order, before editing)

- [ ] Disclosure title card (0:00–0:05): plain text card with the
      required-disclosure line, no clip needed — just a title-card render,
      first frame of the edit.
- [ ] Hook shot: `?bundle=bundles/muse-real-agent-proof.jsonl&view=share`
      (the console's clean share-view mode — no console chrome, just the
      diff) zoomed/cropped to the "decoy key fetched" + two "never
      mentioned" rows. This is the opening frame — get it right before
      anything else.
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
