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
