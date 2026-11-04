# Who this is for, what it replaces, what it costs

Written plainly, with only facts this repository can back. There is **no design partner and no
pricing yet**; nothing below claims otherwise.

## Who has the problem

Teams that let a coding agent change code they then ship: it opens pull requests, runs in CI or
on a developer's laptop with file, shell and network access. The person accountable for that
change (the engineer who merges it, the platform or security owner behind them) currently has
exactly one account of what the agent did: **the agent's own summary**. The two incidents cited in
the README (an agent sandbox escape at a frontier lab, and METR finding agents that spoofed their
own tool calls) are the reason that is uncomfortable.

## Evidence the problem exists

<!--SWEEP-WHO-START-->In our own sweep of 263 real Muse Code sessions (data cutoff 2026-11-04T04:40): when nothing pulled the agent toward the decoy credential, 0/69 sessions touched it. In the red-team arena, where Muse Spark 1.3 and Muse Spark Open wrote the persuasion wording for a setup step in a README, contributing guide or code comment, Muse Code fetched the token in 22/60 sessions and saved it to disk in 3/60. witness's deterministic gate failed 26/26 of the sessions that saved a credential and 0/89 benign sessions (false alarms). A neutral-framing control (same step and same failing test, no persuasion) fetched in 11/12 and saved in 2/12, so persuasion effects are read against that. The attacker model (Muse Spark Open) refused 4 of 14 rewrite requests outright (counted, never run). In round 2 an adaptive attacker (Muse Spark Open, shown only the content-free outcome of round 1) rewrote 10 framings: the agent fetched in 5/20 sessions and saved the token in 1/20, against 11/20 and 0/20 for the same framings in round 1. One agent, a decoy on a local fake service, few sessions per cell..<!--SWEEP-WHO-END-->
That is an agent following a documented setup step and leaving a credential on disk (a deliberately conservative stop
policy), and the thing the merge gate catches. It is one agent and a decoy on a local fake service; a measurement, not a
prevalence in the wild.

## What it replaces

| Today | With witness |
|---|---|
| Trust the agent's final message | A recorder outside the agent's process records files, processes and (decoy-endpoint) network events; the receipt is hash-chained and signed, so the agent's words are never the evidence |
| Read the transcript or diff after the fact, by hand | A merge-gate check that fails on a stop-severity finding, plus an advisory read-out; reviewers open the console only when it flags |
| Tools that retain prompts and responses to audit an agent | Content-free by design (digests, enums, counts); nothing sensitive to store, leak or subpoena |

## What it costs to try

Measured, not estimated:

- **CI time:** the deterministic gate ran in 16 s (PR #1) and 44 s (PR #4) on GitHub-hosted runners.
- **Verification:** a signed receipt verifies in a median 2.5 ms locally (`docs/NUMBERS.md`).
- **Meta model calls** are optional and advisory: 24 s (Spark 1.3 analyst), 12 s (Spark 1.3 triage) and 58 s
  (Glimmer 30B on our Modal GPU) in the captured runs. The open-weight route (Muse Spark Open,
  Glimmer) can be self-served, which swaps a per-call fee for GPU hosting (we use Baseten for Spark Open
  and a Modal GPU for Glimmer; both are paid services). Those figures are for successful calls: the
  README also records timeouts of 54 to 142 s and a ~70 s Glimmer cold start.
- **Adoption:** one GitHub Action step (`.github/actions/witness-verify`) and a recorder wrapper around
  the agent; no prompt or response data leaves the machine.

## What is not proven

- Nobody outside this team has used it. There are no customer numbers, and no cost-per-seat.
- The decoy-credential result shows what witness records, not how often agents misbehave on their own;
  see `docs/NUMBERS.md` for the experiment and its limits.
- The merge gate is only as strong as its trust setup (`docs/LIMITATIONS.md`: pin the signer key).

## Commercial path

The founder also runs AariaSec (runtime monitoring of AI agents, built before this event and not part
of this repository). The intended path is that a build-time witness finding becomes a runtime rule
there. That is planned, not built.
