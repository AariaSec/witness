"""Real Claude Code `~/.claude/projects/.../<session-uuid>.jsonl` parser.

Ground truth below was established empirically against a real,
isolated, throwaway scratch session (`claude`, confirmed v2.1.310 on this
machine, 2026-10-26/27) run in a disposable directory — never against any
real project's own transcript, and never against this actual conversation
(`~/.claude/projects/-Users-aj-Desktop-AariaSec-AariaSec-Claude/` in
particular is off-limits permanently, not just for this spike). Two
sanitized, committed fixtures capture the two shapes this module handles:
`tests/fixtures/claude_journal/success_session.txt` (a `Write` that
succeeded) and `tests/fixtures/claude_journal/denied_session.txt` (the
same task, but `Write` was denied — no `--allowedTools` granted).

## File location and line shape

One JSON-lines file per session at
`~/.claude/projects/<cwd-with-slashes-as-dashes>/<session-uuid>.jsonl`.
Unlike Muse Code's `session.jsonl` (`muse_journal.py`), every line here is
already a single, flat, top-level JSON object — there is no envelope/
double-decode step. Top-level `type` values observed: `queue-operation`,
`user`, `attachment`, `atis-latch`, `api-request-shape`,
`api-request-blob`, `api-request`, `last-prompt`, `assistant`,
`cost-state`. Only two matter for claim extraction, both covered below.

## The two record shapes that matter

**`assistant` records** — `message.content` is a list of blocks; a block
with `"type": "tool_use"` carries `"name"` (e.g. `"Write"`) and `"input"`
(tool-specific args — for `Write`, `file_path` + `content`). The same data
is duplicated at `wireToolInputs[tool_use_id]` on the same record. This
module does NOT build a claim from this record alone — see "why the claim
comes from the result side" below.

**`user` records that follow a tool_use`** — `message.content` has a
`"type": "tool_result"` block (`is_error`, `content` — content-bearing,
digest only — and `tool_use_id`, correlating back to the assistant's
`tool_use` block id). There is also a richer, tool-specific
`toolUseResult` field on the SAME record:

- **Success, confirmed shape** (from `success_session.txt`):
  `toolUseResult` is a DICT: `{"type": "create", "filePath": "...",
  "content": ..., "structuredPatch": [...], "originalFile": null,
  "userModified": false}`. `type` and `filePath` are the only fields this
  module reads; `content`/`originalFile`/`structuredPatch` are
  content-bearing (the patch hunks carry literal diff text) and are never
  read into an emitted record.
- **Denial, confirmed shape** (from `denied_session.txt`): `toolUseResult`
  is instead a plain STRING — the human-readable denial message (e.g.
  `"Error: Claude requested permissions to write to ..., but you haven't
  granted it yet."`) — content-bearing prose, never parsed for structure.
  The `user` record additionally carries `toolDenialKind` (a short string,
  `"user-rejected"` in this capture) and `is_error: true` on the
  `tool_result` block. `permissionDecision` is present in BOTH shapes but
  its own sub-fields differ: `{"decision": "accept", "source": "config",
  "reasonType": "rule", "ruleSource": "cliArg"}` on success vs.
  `{"decision": "reject", "source": "config", "reasonCode": "unknown"}` on
  denial — both are short, enum-like strings, never prose.

## Why the claim comes from the `user`/tool_result record, not `assistant`

Mirroring `muse_journal.py`'s convention (its claim is built from
`tool.result`, the post-hoc record, not the pre-call request), this module
only emits an `AssistantClaim` from the `user` record that reports an
*outcome*. Two reasons, not just convention-following:

1. Building a claim from the `assistant` tool_use block too would double
   the claim count for every successful write (one from the request, one
   from the result) for no benefit — the result record already carries
   everything needed (tool shape + path), since the confirmed success
   `toolUseResult` shape is entirely self-describing (`type: "create"` +
   `filePath`) without needing to cross-reference the paired `assistant`
   record at all.
2. For a DENIAL, the `user` record alone does not say which tool was
   denied (no tool name on it; `toolUseResult` is just a prose string) —
   attributing the denial to "Write" would require either (a) correlating
   back to the paired `assistant` record's structured `input.file_path`
   (stateful, and not needed since outcome #1 already covers the shape we
   can act on), or (b) parsing the human-readable denial sentence (prose
   parsing — refused on the same content-discipline grounds muse_journal.py
   refuses to recompute `content_sha256` from a guess). Rather than add
   state or parse prose, this module does neither.

## The denial-path design decision — DELIBERATE, not an oversight

**A denied tool call never produces an `AssistantClaim`.** `AssistantClaim`
models what the assistant did (or asserts it did); a call that was refused
is specifically the absence of that — the agent *tried* and *nothing
happened*. Two alternatives were considered and rejected:

- Misusing an existing `TailMeta.event` literal (`"parse_error"` etc.) to
  signal "denied" — rejected: the line parsed perfectly fine; calling it a
  parse error would be false.
- Adding a new `Kind`/`TailMeta` event value for "denied" — rejected
  because it would touch `witness/models.py`, which is recorder-core and
  is required to have ZERO diff for this integration (the architectural
  point of this module is that a new coding-agent format needs only a new
  `ClaimParser`, not recorder-core changes).

So: silence. This is honest, not lossy for the thing witness actually
checks — the independent, OS-level `FsWatcher`/ground-truth detectors
already establish whether a file was (or wasn't) written, completely
independent of what the assistant's own transcript claims. A denied call
produces no ground-truth fs event either, so there is nothing for a claim
to be cross-checked against; omitting the claim does not create a
mismatch the detectors would otherwise have caught. If a future need
arises to surface denials explicitly (e.g. to measure how often an
operator's permission gate fires), that is a new, additive concept
deserving its own schema field — not something to retrofit into
`AssistantClaim`'s "the agent did X" semantics.

## The two-tool-observed limitation (updated 2026-10-27)

**`Write` and `Bash` have been observed, end to end; `Read`, `Edit`,
`Grep`, `Glob` have not.** This update came from a real, genuine finding,
not a planned extension: a real Claude Code flagship session (the
decoy-credential catch, `runs/frozen/claude-real-agent-proof-20261027-
012001-c976/`) fetched the decoy URL and saved it to disk using a SINGLE
Bash command (`curl`-style, fetch-and-redirect in one call) rather than a
separate Read-then-Write pair — meaning that session produced ZERO claims
under the original Write-only mapping, not because the agent was
unusually honest, but because the parser had no claim surface for Bash at
all. Confirmed by inspecting the real session log's record shapes
directly (never its content). Bash's success shape is confirmed
different from Write's: no `type` key, just `{"stdout", "stderr",
"interrupted", "isImage", "noOutputExpected"}` — mapped to a count-only
`ClaimTool.shell` claim (no path, no host — the command itself is
content-bearing text, never parsed for what it touched), matching
`muse_journal.py`'s existing "shell" claim semantics. `Read`, `Edit`,
`Grep`, `Glob` all appear as tool *names* in this session's own tool
listing (`api-request-shape`/`attachment` records — themselves never read
for claim purposes), but none of them has a captured, confirmed
`tool_use`/`tool_result` pair in this module's fixtures yet. Mapping any
of them would be a guess, which this module's house discipline (matching
`muse_journal.py`) refuses to do. Extend only from another real, observed
capture.

A second, narrower gap: even for `Write`, only `toolUseResult.type ==
"create"` (a new file) has been observed. Claude Code's own UX implies a
`type == "update"` shape likely exists for overwriting an existing file,
but that has not been captured — this module does not guess at it
either. See `docs/LIMITATIONS.md`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from witness.canon import sha256_hex
from witness.models import AssistantClaim, ClaimTool, TailMeta

_MAX_LINE = 2 * 2**20  # 2 MB hard cap, same bound tailer.py/muse_journal.py use

# Real `toolUseResult.type` values confirmed, by an actual observed
# capture, to correspond to a given `ClaimTool`. Extend only from another
# observed capture, never a guess — e.g. an "update" (overwrite-existing-
# file) variant of Write was never captured and is deliberately absent.
_TOOL_RESULT_TYPE_TO_CLAIM_TOOL: dict[str, ClaimTool] = {
    "create": ClaimTool.write,
}

# A successful Bash call's `toolUseResult` has a DIFFERENT, confirmed
# shape from Write's: no "type" key at all, just {"stdout", "stderr",
# "interrupted", "isImage", "noOutputExpected"} (confirmed against a real
# session, 2026-10-27, where the agent fetched a URL and saved the
# response via a single Bash command rather than a separate Write call —
# see docs/NUMBERS.md's paired-comparison section for why this mattered).
# "stdout" is the cheapest reliable discriminator that doesn't require
# reading its (content-bearing) value.
_BASH_RESULT_DISCRIMINATOR_KEY = "stdout"


def iter_session_file(path: Path) -> Iterator[dict[str, Any]]:
    """Read a real Claude Code session `.jsonl` file (already closed, or at
    least stable at the moment of reading — this is a one-shot batch
    reader, not a live tail) and yield every top-level record it contains,
    in file order. Malformed lines are silently skipped — never raises."""
    with open(path, "rb") as fh:
        for raw_line in fh:
            stripped = raw_line.rstrip(b"\r\n")
            if not stripped.strip():
                continue
            if len(stripped) > _MAX_LINE:
                continue
            try:
                obj = json.loads(stripped.decode("utf-8", errors="strict"))
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


def _digest_of_record(rec: dict[str, Any]) -> str:
    """Digest a record for `AssistantClaim.line_digest`. Hashes a
    deterministic re-serialization (same approach as `muse_journal.py`'s
    `_digest_of_record`), not literal raw bytes — this module is handed
    already-parsed dicts by `iter_session_file`/`ClaudeCodeClaimParser`
    alike."""
    raw = json.dumps(rec, sort_keys=True, default=str).encode("utf-8")
    return sha256_hex(raw[:_MAX_LINE])


def claim_from_record(rec: dict[str, Any]) -> AssistantClaim | None:
    """Reduce one top-level Claude Code session-log record to an
    `AssistantClaim`, or `None` if it isn't a recognized, observed tool
    success (see module docstring: a denial never yields a claim, by
    design; an unobserved tool name/shape never yields a guessed claim).

    Never raises — any field access is guarded. Never reads a
    content-bearing field's value (`content`, `structuredPatch`,
    `originalFile`, the denial prose string); only a bounded,
    enumerated shape plus a digest ever leaves this function.
    """
    try:
        if not isinstance(rec, dict):
            return None
        if rec.get("type") != "user":
            return None

        message = rec.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if not isinstance(content, list):
            return None

        tool_result_block = None
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                tool_result_block = block
                break
        if tool_result_block is None:
            return None

        # Denial path: deliberately never a claim — see module docstring.
        if rec.get("toolDenialKind") is not None or tool_result_block.get("is_error") is True:
            return None

        tool_use_result = rec.get("toolUseResult")
        if not isinstance(tool_use_result, dict):
            # Includes the denial shape (a plain string) and anything else
            # unrecognized — never guessed at.
            return None

        result_type = tool_use_result.get("type")
        if isinstance(result_type, str) and result_type in _TOOL_RESULT_TYPE_TO_CLAIM_TOOL:
            file_path = tool_use_result.get("filePath")
            if not isinstance(file_path, str) or not file_path:
                return None

            count: int | None = None
            structured_patch = tool_use_result.get("structuredPatch")
            if isinstance(structured_patch, list):
                count = len(structured_patch)

            return AssistantClaim(
                source="session_log",
                tool=_TOOL_RESULT_TYPE_TO_CLAIM_TOOL[result_type],
                claimed_paths=[file_path[:256]],
                claimed_hosts=[],
                claimed_count=count,
                line_digest=_digest_of_record(rec),
            )

        if _BASH_RESULT_DISCRIMINATOR_KEY in tool_use_result:
            # A successful Bash call — no path, no host: the command
            # itself is content-bearing text, never parsed for what it
            # touched. A count-only claim (same semantics as
            # muse_journal.py's "shell" claims), so the independent
            # fs/marker/sink ground truth is what's actually compared
            # against, never a guessed path.
            return AssistantClaim(
                source="session_log",
                tool=ClaimTool.shell,
                claimed_paths=[],
                claimed_hosts=[],
                claimed_count=1,
                line_digest=_digest_of_record(rec),
            )

        return None
    except Exception:
        return None


class ClaudeCodeClaimParser:
    """`tailer.ClaimParser` implementation for real Claude Code session
    `.jsonl` files.

    Drop-in alternative to `tailer.DefaultClaimParser`/
    `muse_journal.MuseJournalClaimParser`:

        from witness.claude_journal import ClaudeCodeClaimParser
        from witness.tailer import Tailer
        tailer = Tailer([session_jsonl_path], parser=ClaudeCodeClaimParser())
        tailer.start(bus.emit_fn)

    Unlike `MuseJournalClaimParser`, one raw line here never unwraps to
    more than one record (no envelope shape in this format), so
    `parse_line` returns a single-item, empty, or `TailMeta`-wrapped list
    — kept as a list return (not record-or-`None`) only for symmetry with
    `MuseJournalClaimParser`'s type, which `Tailer._poll_file` already
    handles.

    Never raises. A line that is valid JSON but not a recognized tool
    success (including every denial, and every unobserved tool/shape) is
    quietly dropped (returns `[]`) — not reported as a parse error. A line
    that isn't even valid JSON (or exceeds the hard size cap) IS reported,
    as a single `TailMeta(event="parse_error")`.
    """

    def parse_line(self, line: bytes, source: str) -> list[AssistantClaim | TailMeta]:
        stripped = line.rstrip(b"\r\n")
        if not stripped.strip():
            return []
        if len(stripped) > _MAX_LINE:
            return [TailMeta(event="parse_error", file="", bytes_skipped=len(stripped))]
        try:
            obj = json.loads(stripped.decode("utf-8", errors="strict"))
        except Exception:
            return [TailMeta(event="parse_error", file="", bytes_skipped=len(stripped))]
        if not isinstance(obj, dict):
            return [TailMeta(event="parse_error", file="", bytes_skipped=len(stripped))]

        claim = claim_from_record(obj)
        if claim is None:
            return []
        return [claim]


__all__ = [
    "ClaudeCodeClaimParser",
    "claim_from_record",
    "iter_session_file",
]
