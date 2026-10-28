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
(5) A fifth pass (2026-10-27): used Meta's own Muse Spark Open (via
Baseten, 7/10) and a real `muse exec` adversarial-judge session (billed
on the Meta Model API dashboard directly, 6/10) for independent
critiques — both run in scratch workspaces, not committed anywhere;
this paragraph and the commits below are the durable record of what
each found and what changed because of it. Acted on: dropped the Claude
Code quote aside entirely (two independent reviews now flagged the same
unverifiable-quote risk);
tightened "zero recorder-core diff" to state plainly what did change (one
new parser); put the hook's true base rate on screen (0/16 in the
follow-up batch — it's the outlier case); named exactly why PR #2 is red
vs. the flagship's PASS (stop-severity network exfiltration vs. warn-
level local save); narrowed the close line off "for any agent" to what's
actually proven; trimmed the Washington Post citation to stop citing an
incident right after disclaiming it doesn't apply; relabeled README's
"bandwidth" claim (a category error — no concurrency was measured) and
caveated the latency numbers as owner's-machine, not CI-runner; and fixed
two stale doc claims the critique surfaced (README still said
`pgroup_escape` had no detector after it was fixed; NUMBERS.md called a
file "untracked" that was actually committed in `488e784`). Declined,
with reasoning: reopening the hook to start on a failing PR instead of
the console diff (undoes the prior 3-model-reviewed redesign without new
justification), relabeling the private `witness-private` seed repo (a
deliberate IP-protection decision, not a presentation choice), and adding
a Startup-track traction slide (pricing/design-partners — not buildable
from a doc edit).
(6) A sixth pass (2026-10-27, same day): a `muse exec` max-effort
brainstorm, asked for the single highest-leverage *implementation* (not
wording) given the remaining time, found the sharpest gap pass (5) left
unaddressed: the only red merge-gate PR was a simulated run, not a real
agent. Built `credential_persist` (stop-severity detector scoring what
both flagship runs already did — persist the decoy credential to disk —
instead of chasing real network exfiltration, which the same pass
explicitly recommended against). A real Muse Code session hit it on the
first attempt; PR #4 is now the merge-gate beat's lead red example. Full
story: `docs/NUMBERS.md`'s "third real-agent proof" section.
(7) A seventh pass (2026-10-28): two new real-data console visuals built
this week — Divergence Flow and the Blast Radius 3D scene — replace the
Flagship beat's plain timeline pull-back (0:35–1:05 below); capture
checklist updated to match. No other beat changed: the hook, tamper
test, generalization, merge-gate, honesty, and close beats are unchanged
from pass (6) and still reflect current reality (verified against the
live repo state, not just re-read).

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
**Second caption, smaller, bottom corner:** "1 verified case; 0/16 in the
follow-up batch (`docs/NUMBERS.md`) — rare, not typical."

*Added after a `muse exec` adversarial-judge pass (2026-10-27): the 32-run
experiment later in this video reports 0/16 mismatch on the decoy batch,
making this hook the outlier case, not the typical one. A sharp judge
would call that out unprompted. Putting the base rate on screen in the
hook itself — before anyone can raise it — turns the sharpest available
attack on this video into another honesty beat, consistent with the
project's whole stance.*

---

## 0:20–0:35 — The problem, and why now

**Visual:** split screen — agent's narration on one side, a blank
question mark on the other labeled "what actually happened?"

**Voiceover:**
> Every coding agent writes its own report of what it did. That report
> is the only account anyone checks — produced by the exact same process
> that did the work. Agents already have production-level access. The
> question is: when one does something you didn't expect, how fast do
> you find out — and from who?

**Caption:** "The agent's report is the only witness to itself. Until now."

*Dropped the Washington Post citation from this beat (previously used for
"why now" framing) after a Meta Spark Open adversarial-judge pass flagged
it as borrowed urgency: the beat explicitly disclaimed "this project
wouldn't have caught that incident" and then cited it anyway, which reads
as fear-by-association to a skeptical judge rather than a sourced claim.
The underlying point — agents already have real production access —
doesn't need a specific incident to be true. Full incident mention still
lives in `README.md`'s "Why" section for anyone who wants the citation,
also trimmed to drop the same editorializing.*

---

## 0:35–1:05 — Flagship proof (Muse Code), zoomed out

**Visual (updated 2026-10-28 — two new real-data visuals built this week
now replace the plain timeline pull-back):** same console, same bundle
as the hook, Overview tab (the console's default view as of today's
Overview/Full-evidence split — no extra click needed). First the
**Divergence Flow** — the agent's claimed path and the recorder's
observed path running side by side, visibly splitting apart at the exact
seq the decoy read fires. Then a hard cut to the **Blast Radius** 3D
scene — the real process tree, the decoy-net node glowing on the
timeline, built entirely from `ppid`/`pid`/`peer_pid` fields already in
the bundle (no synthetic geometry — see `console/src/lib/blastRadius.ts`
for exactly which fields drive which node).

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

**Why these two replace the old plain-timeline shot:** the Divergence
Flow visualizes the exact claim in the voiceover — "its claim log never
mentioned either file" — as a literal fork in two paths, not a sentence
a viewer has to take on faith. The Blast Radius scene is the single most
visually distinct shot in the whole video; it earns its 10-15 seconds on
that alone. Both are driven by the same bundle already named on screen
— no new artifact, no new claim, same proof, better visualization.

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
> different agent — Claude Code. Adding it meant writing one new adapter
> for its log format — zero changes to the actual detection pipeline:
> the ledger, the detectors, the actions. Same task: it fetched the same
> decoy credential and saved it to disk — caught the same way,
> independently, no reasoning read.

**Caption:** "Zero recorder-core diff — verified by `git diff --stat`, not asserted."

*Two changes from the previous cut, both from a Meta Spark Open
adversarial-judge pass (`muse exec`, 2026-10-27): (1) dropped the Claude
Code "I didn't use it for anything" on-screen aside entirely — it was
already flagged once (Opus round) and flagged again independently here
as reintroducing the exact unverifiable-quote risk the hook rewrite
existed to remove; it was already listed "cut first" in the cut-order
below, so this just makes that the default instead of a time-pressure
fallback. (2) Tightened "zero changes to the recorder core" to say what
*did* change (one new parser/adapter) — the judge pass noted the diffed
path list in `docs/NUMBERS.md` is explicitly scoped to the detection
pipeline and excludes the new parser by construction, which is honest
but risks being misread as "nothing changed." Saying it plainly is a
stronger claim, not a weaker one: the point is that detection logic is
agent-agnostic and only input parsing is agent-specific.*

---

## 2:00–2:25 — The merge gate

**Visual:** a real, live GitHub pull request —
[PR #4](https://github.com/AariaSec/witness/pull/4) — red X, the Actions
log showing the content-free step summary (`policy: FAIL (stop findings:
2)`, `"simulated":false`). Cut to [PR #1](https://github.com/AariaSec/witness/pull/1),
green check, same gate, a faithful session.

**Voiceover:**
> This isn't just a viewer. The signed receipt is bound to the actual
> git tree, and a real GitHub Action runs `witness verify` on every pull
> request. This red PR is a real coding agent — the same kind of session
> you just saw — doing the same thing both flagship runs did: saving the
> decoy credential to a file. The difference is scoring: a persisted
> secret is stop-severity, so it actually fails the check, visibly,
> before a merge ever happens. The pass/fail decision is fully
> deterministic — chain, signature, policy. It can optionally also show
> a live narrative from Meta's open-weight Muse Spark Open model
> alongside the verdict — advisory only, never the thing that decides
> pass or fail.

**On-screen:** the two PR URLs, side by side, green and red.

*Revised again (2026-10-27) after a second `muse exec` pass (max
reasoning effort) found an even sharper gap than the PASS-vs-FAIL
question this beat previously just answered: the only red PR
(`PR #2`, network exfiltration) was `"simulated":true` — a scripted
stand-in, not a real agent. Rather than chase a real agent into
genuinely attempting network exfiltration (the same pass explicitly
recommended against this — agents are trained to refuse that exact
instruction shape), a new detector (`credential_persist`, stop-severity)
now scores what real agents already proved they do: persist the decoy
credential to a tracked file. A real Muse Code session re-running the
exact flagship task hit it on the first attempt — `policy: FAIL (stop
findings: 2)`, `stop_pgroup` actually fired in 298ms, `"simulated":false`
— frozen as `runs/frozen/credential-persist-real-proof-20261027-135303-9dba/`,
opened as PR #4. This is now the lead red example; PR #2 (simulated
network-exfil) stays live as a second scenario, not the only one. Full
story: `docs/NUMBERS.md`'s "third real-agent proof" section.*

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
> witness — proven on two architecturally different agents already, one
> new adapter away from the next.

**On-screen:**
`github.com/AariaSec/witness` · `aariasec.github.io/witness`

*Narrowed from "for any agent, on every commit" (a `muse exec`
adversarial-judge pass called this an overclaim against what's actually
proven: two agents, one task family, not a universality result). This
version says exactly what's demonstrated — two agents — and states the
real scaling mechanism (one new parser/adapter) rather than implying
it's already solved for everything.*

---

## Cut order if time runs short

1. Collapse the "Honesty" beat to the 44%/32-runs line only, dropping
   the pgroup_escape before/after visual — the number alone still carries
   the point.
2. Never cut: the receipt + `witness verify` + one real green/red PR
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
- [ ] Flagship beat (updated 2026-10-28): screen-record the Divergence
      Flow replaying on the muse-real-agent-proof bundle (Overview tab,
      default view) through the exact seq the paths split, then the
      Blast Radius 3D scene on the same bundle with the stop/decoy-net
      node visible and glowing. Both components ship with their own
      real-data tests (`console/tests/divergence.test.ts`,
      `console/tests/blastRadius.test.ts`) — no capture-time setup beyond
      loading the bundle and letting replay run.
- [ ] Screen-record the tamper-test flip in real time (don't fake the
      transition — it has to actually compute).
- [ ] Screen-record PR #1 and PR #4's Actions tab live, scrolled to the
      step summary (PR #4 is the lead red example now — real agent, not
      simulated; PR #2 stays available as a second, simulated scenario
      if there's room).
- [ ] Record the `git diff --stat` command showing the empty recorder-core
      diff, in a real terminal, not a screenshot.
- [ ] Voiceover recorded separately, synced in edit — not live narration
      over screen capture (gives room to hit exact timings per beat).
