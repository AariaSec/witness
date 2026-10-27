"""Real Muse Code `session.jsonl` journal parser.

Ground truth below was established empirically against a real, locally
installed `muse` binary (Meta's Muse Code CLI, v1.4.13) on 2026-10-26, using
only sanctioned, content-free commands (`muse exec --provider echo --json`,
`muse plugins validate`) — never a live, tool-executing session. See
`docs/LIMITATIONS.md` for the one thing this *cannot* establish safely: the
real shape of a tool-call hook payload, since `--provider echo` never
invokes a tool and running a real tool-executing session is out of scope
for this build (see the project's safety boundary).

## File location

```
${XDG_DATA_HOME:-$HOME/.local/share}/muse/sessions/YYYY/MM/DD/<session-id>/session.jsonl
.../subagent/<child-session-id>/session.jsonl
```

## Line shape — NOT uniformly enveloped

Three independent real captures (a top-level session and two of its
subagent sessions) all showed the same pattern: the **large majority** of
lines are already a flat inner record —

```json
{"schema_version":1,"id":"<uuid>","stream":{"kind":"session","id":"<uuid>"},
 "sequence":<int>,"recorded_at":<int>,"record_type":"event","durability":"durable",
 "causation_id":"<uuid>|null","payload_type":"<dotted.string>",
 "payload_schema_version":1,"payload":{"kind":"<snake_case>", ...}}
```

— and a **small minority** (observed: exactly the session-opening
`session_permission_transaction`, once per session) are a `retained_frame`
envelope whose `children[].record_json` is a JSON-encoded STRING that must
be parsed a SECOND time to reach an inner record of the same shape above:

```json
{"retained_frame":"session_permission_transaction","frame_schema_version":1,
 "outer_log_ordinal":1,"transaction_id":"<uuid>",
 "children":[{"child_index":0,"record_json":"<json-string>"}, ...],
 "content_sha256":"sha256:<hex>"}
```

This corrects an earlier assumption (carried in an older architecture
draft) that *every* line is envelope-wrapped — it isn't. `unwrap_line`
below handles both shapes uniformly.

`content_sha256` on an envelope line: present, but its preimage is NOT
determined here. Several plausible reconstructions were tried empirically
(sha256 of the concatenated `record_json` strings; of the envelope object
minus that field, both sorted-key and as-is; of the `children` array alone;
of the re-serialized inner records) and none matched the real value. Rather
than guess further or fake a verification, this module does not attempt to
recompute/verify `content_sha256` — it is surfaced unexamined via
`EnvelopeFrame.content_sha256` for a caller that wants to reason about it
independently. This is an honest gap, not an oversight — see
`docs/LIMITATIONS.md`.

## Content-bearing fields — confirmed, must never be stored raw

Empirically confirmed fields that carry literal prompt/response text in a
real session.jsonl (RULE-1 analog: witness must never persist these):

- `payload.event.prompt` (payload_type `runtime.session`, `payload.kind`
  `"run"`, `payload.event.kind` `"started"`)
- `payload.model_messages[].content[].text` and `payload.refill_blocks[].text`
  (payload_type `runtime.user_intent.accepted`)
- `payload.event.text` (payload_type `runtime.session`, `payload.kind`
  `"run"`, `payload.event.kind` `"context_block_updated"` — full system/
  developer context block text, can be tens of KB)
- `payload.event.text` (payload_type `runtime.session`, `payload.kind`
  `"run"`, `payload.event.kind` `"assistant_message_committed"` — the
  assistant's own response text)

This parser never reads these fields' *values* into any emitted record —
only a bounded, enumerated shape plus a digest ever survives, mirroring
`tailer.py`'s own discipline for the simulated-agent format.

## What this parser does NOT yet do (the tool-call gap)

**Partially closed 2026-10-26.** A real, tool-executing session (`muse
exec --provider meta --trust-workspace --disable-approval`, run by the
user directly — not by this codebase, which stays within its own
sandbox-preserving boundary) produced a genuine `tool.result` record:

```json
{"payload_type":"tool.result","payload":{"kind":"tool_result",
 "call_id":"call_...","text":"<content-bearing, never stored>",
 "edit_facts":{"tool_name":"write_file","path":"hello.txt","added":1},
 "correlation_facts":{"tool_name":"write_file","outcome":"success"}}}
```

`correlation_facts.tool_name` is the clean, enumerable signal —
`_PAYLOAD_TYPE_TO_CLAIM_TOOL` now maps the one tool_name actually
observed, `"write_file"` → `ClaimTool.write`, extracting
`edit_facts.path` (bounded, truncated — a path, not content) and
`edit_facts.added` as `claimed_count`. `payload.text` is a content-bearing
field (confirmed here, not guessed) and is never read into any emitted
record, same discipline as every other content field in this module.

**Still genuinely open:** only `write_file` has been observed. Other
`tool_name` values (a shell command, a file read, a web request) were
never exercised in this one capture and are NOT guessed at —
`_PAYLOAD_TYPE_TO_CLAIM_TOOL` has exactly one entry, not a speculative
full set. See `docs/LIMITATIONS.md`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from witness.canon import sha256_hex
from witness.models import AssistantClaim, ClaimTool, TailMeta

_MAX_LINE = 2 * 2**20  # 2 MB hard cap, same bound tailer.py uses

# Real payload_type values confirmed to correspond to an assistant TOOL
# claim, mapped to the existing `ClaimTool` enum. Extend only from an
# observed capture; never from a guess. `"tool.result"` is handled
# specially in `_claim_tool_for` (its ClaimTool depends on
# `correlation_facts.tool_name`, see `_TOOL_NAME_TO_CLAIM_TOOL`), so it is
# deliberately NOT listed here.
_PAYLOAD_TYPE_TO_CLAIM_TOOL: dict[str, ClaimTool] = {}

# Real `payload.correlation_facts.tool_name` values (payload_type
# `"tool.result"`) confirmed, by an actual observed capture, to correspond
# to a given `ClaimTool`. Confirmed 2026-10-26 against a real
# `muse exec --provider meta` session: `write_file` creating a new file.
# Extend only from another observed capture — a shell command, a file
# read, a web request were never exercised and are not guessed at here.
_TOOL_NAME_TO_CLAIM_TOOL: dict[str, ClaimTool] = {
    "write_file": ClaimTool.write,
}

# Real `payload.event.kind` values (nested under a `runtime.session`
# payload whose own `kind` is `"run"`) confirmed to correspond to a tool
# claim. Same rule: empty until observed.
_RUN_EVENT_KIND_TO_CLAIM_TOOL: dict[str, ClaimTool] = {}


def unwrap_line(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Unwrap one already-JSON-parsed `session.jsonl` line object into zero
    or more inner MSP records.

    Handles both real shapes (see module docstring): a flat inner record
    (returned as a 1-element list) or a `retained_frame` envelope (each
    `children[].record_json` string is parsed a second time; entries that
    fail to parse, or aren't objects, are silently dropped — never
    raises). Anything that is neither shape yields an empty list.
    """
    if obj.get("retained_frame") is not None:
        out: list[dict[str, Any]] = []
        children = obj.get("children")
        if not isinstance(children, list):
            return out
        for child in children:
            if not isinstance(child, dict):
                continue
            rec_json = child.get("record_json")
            if not isinstance(rec_json, str):
                continue
            try:
                inner = json.loads(rec_json)
            except Exception:
                continue
            if isinstance(inner, dict):
                out.append(inner)
        return out

    # Flat shape: a real inner record always carries these three keys
    # together (confirmed across every non-envelope line observed).
    if "payload_type" in obj and "payload" in obj and "sequence" in obj:
        return [obj]
    return []


def iter_inner_records(line: bytes) -> list[dict[str, Any]]:
    """Pure parse of one raw `session.jsonl` line (bytes) into zero or more
    inner MSP record dicts. Never raises."""
    try:
        if len(line) > _MAX_LINE:
            return []
        obj = json.loads(line.decode("utf-8", errors="strict"))
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    return unwrap_line(obj)


def iter_session_file(path: Path) -> Iterator[dict[str, Any]]:
    """Read a real `session.jsonl` file (already closed/rotated — this is
    a one-shot batch reader, not a live tail) and yield every inner record
    it contains, in file order. Malformed lines are silently skipped —
    never raises, mirrors `iter_inner_records`."""
    with open(path, "rb") as fh:
        for raw_line in fh:
            stripped = raw_line.rstrip(b"\r\n")
            if not stripped.strip():
                continue
            yield from iter_inner_records(stripped)


def _digest_of_record(rec: dict[str, Any]) -> str:
    """Digest an inner record for `AssistantClaim.line_digest`. The
    original raw bytes of an enveloped child aren't preserved past the
    double-JSON-decode, so (like `tailer.parse_json_output`) this hashes a
    deterministic re-serialization rather than claiming to hash "the raw
    line" verbatim."""
    raw = json.dumps(rec, sort_keys=True, default=str).encode("utf-8")
    return sha256_hex(raw[:_MAX_LINE])


def _claim_tool_for(rec: dict[str, Any]) -> ClaimTool | None:
    """Defensible-mapping lookup only — see module docstring. Returns
    `None` for every payload_type/event_kind/tool_name this module has not
    actually observed to be a tool claim."""
    payload_type = rec.get("payload_type")
    if isinstance(payload_type, str) and payload_type in _PAYLOAD_TYPE_TO_CLAIM_TOOL:
        return _PAYLOAD_TYPE_TO_CLAIM_TOOL[payload_type]

    payload = rec.get("payload")
    if isinstance(payload, dict):
        if payload_type == "tool.result":
            correlation = payload.get("correlation_facts")
            if isinstance(correlation, dict):
                tool_name = correlation.get("tool_name")
                if isinstance(tool_name, str) and tool_name in _TOOL_NAME_TO_CLAIM_TOOL:
                    return _TOOL_NAME_TO_CLAIM_TOOL[tool_name]

        if payload.get("kind") == "run":
            event = payload.get("event")
            if isinstance(event, dict):
                event_kind = event.get("kind")
                if isinstance(event_kind, str) and event_kind in _RUN_EVENT_KIND_TO_CLAIM_TOOL:
                    return _RUN_EVENT_KIND_TO_CLAIM_TOOL[event_kind]
    return None


def claim_from_inner_record(rec: dict[str, Any]) -> AssistantClaim | None:
    """Reduce one inner MSP record to an `AssistantClaim`, or `None` if it
    parsed fine but isn't (yet, defensibly) recognizable as a tool claim.
    Never raises — any field access is guarded. Never reads a
    content-bearing field's value (see module docstring); only bounded,
    enumerated shape plus a digest ever leaves this function."""
    try:
        if not isinstance(rec, dict):
            return None
        tool = _claim_tool_for(rec)
        if tool is None:
            return None

        payload = rec.get("payload")
        payload = payload if isinstance(payload, dict) else {}

        # Bounded, content-free extraction only — a path string and an
        # integer count, never `payload.text` (content-bearing, see
        # module docstring) or any other free-text field.
        paths: list[str] = []
        hosts: list[str] = []
        count: int | None = None

        if rec.get("payload_type") == "tool.result":
            edit_facts = payload.get("edit_facts")
            if isinstance(edit_facts, dict):
                path = edit_facts.get("path")
                if isinstance(path, str):
                    paths = [path]
                added = edit_facts.get("added")
                if isinstance(added, int):
                    count = added
        elif isinstance(payload.get("count"), int):
            count = payload["count"]

        return AssistantClaim(
            source="session_log",
            tool=tool,
            claimed_paths=[str(p)[:256] for p in paths][:50],
            claimed_hosts=[str(h)[:255] for h in hosts][:50],
            claimed_count=count,
            line_digest=_digest_of_record(rec),
        )
    except Exception:
        return None


class MuseJournalClaimParser:
    """`tailer.ClaimParser` implementation for real Muse Code
    `session.jsonl` files.

    Drop-in alternative to `tailer.DefaultClaimParser`:

        from witness.muse_journal import MuseJournalClaimParser
        from witness.tailer import Tailer
        tailer = Tailer([session_jsonl_path], parser=MuseJournalClaimParser())
        tailer.start(bus.emit_fn)

    One raw line can unwrap to zero, one, or several inner records (an
    enveloped permission-transaction line has two), so `parse_line` returns
    a *list* rather than a single record-or-`None` — `Tailer._poll_file`
    handles both return shapes (see `tailer.py`).

    Never raises. A line that is valid JSON but not a recognized record
    shape is quietly dropped (returns `[]`) — not reported as a parse
    error, mirroring how `DefaultClaimParser` silently drops a
    structurally-fine-but-unrecognized claim object. A line that isn't
    even valid JSON (or exceeds the hard size cap) IS reported, as a
    single `TailMeta(event="parse_error")`.
    """

    def parse_line(
        self, line: bytes, source: str
    ) -> list[AssistantClaim | TailMeta]:
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

        inner_records = unwrap_line(obj)
        out: list[AssistantClaim | TailMeta] = []
        for rec in inner_records:
            claim = claim_from_inner_record(rec)
            if claim is not None:
                out.append(claim)
        return out


__all__ = [
    "MuseJournalClaimParser",
    "claim_from_inner_record",
    "iter_inner_records",
    "iter_session_file",
    "unwrap_line",
]
