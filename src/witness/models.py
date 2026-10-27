"""Pydantic models for witness ledger records.

Every record in this module is intentionally content-free: no field may
carry raw prompt/response text, file contents, or free-form prose. Fields
are digests (sha256 hex), enums, counts, short bounded paths/hostnames, or
timestamps. `ConfigDict(extra="forbid", frozen=True)` is the first
content-leak defence — an unknown field can never silently enter a record,
and once constructed a record cannot be mutated in place (the ledger
produces a *new* frozen instance when it assigns seq/ts/prev/digest).

Schema is law: do not rename fields or change the discriminated union
without updating `schemas/allowed_keys.yaml` and bumping
`BUNDLE_SCHEMA_VERSION` in `witness/__init__.py`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Kind(StrEnum):
    """Discriminator for every record kind stored in the ledger."""

    manifest = "manifest"
    marker_read = "marker_read"
    outbound_post = "outbound_post"
    fs_event = "fs_event"
    proc_event = "proc_event"
    assistant_claim = "assistant_claim"
    tail_meta = "tail_meta"
    finding = "finding"
    action_result = "action_result"
    clock_warning = "clock_warning"
    run_end = "run_end"
    receipt = "receipt"
    report = "report"


class FsOp(StrEnum):
    create = "create"
    modify = "modify"
    delete = "delete"
    move = "move"
    write_denied = "write_denied"


class ProcOp(StrEnum):
    spawn = "spawn"
    exit = "exit"
    exec = "exec"
    opaque = "opaque"
    escape = "escape"


class ClaimTool(StrEnum):
    read = "read"
    write = "write"
    edit = "edit"
    shell = "shell"
    http = "http"
    search = "search"
    other = "other"


class FindingKind(StrEnum):
    marker_read = "marker_read"
    outbound_post = "outbound_post"
    mismatch = "mismatch"
    protected_write = "protected_write"
    pgroup_escape = "pgroup_escape"
    drift = "drift"


class Severity(StrEnum):
    info = "info"
    warn = "warn"
    stop = "stop"


# A sha256 hex digest — the only way raw content may ever be referenced.
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

# Relative-to-lab path. Bounded length, no newlines — never a vehicle for
# prose or a full raw line of captured text.
RelPath = Annotated[str, StringConstraints(max_length=256, pattern=r"^[^\n\r]*$")]

# A bare hostname (or host:port[/path]) claimed by the assistant or used as
# a decoy destination — bounded, single-line, never a vehicle for request
# bodies or prose.
HostStr = Annotated[str, StringConstraints(max_length=255, pattern=r"^[^\n\r]*$")]

# A git commit sha — 40 hex chars (sha1) or 64 hex chars (sha256 git) —
# bounded, single-line, never a vehicle for prose.
GitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")]


class Base(BaseModel):
    """Common envelope for every ledger record.

    `seq`, `ts_wall`, `ts_mono`, `prev`, and `digest` are assigned by
    `Ledger.append` — callers construct records with the placeholder
    defaults below and the ledger returns a new, fully-populated instance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    seq: int = -1
    kind: Kind
    ts_wall: float = 0.0
    ts_mono: float = 0.0
    prev: Digest | None = None
    digest: Digest | None = None


class Manifest(Base):
    kind: Literal[Kind.manifest] = Kind.manifest
    bundle_schema: str
    witness_version: str
    run_id: str
    platform: Literal["darwin", "linux"]
    marker_port: int
    sink_port: int
    lab_root_digest: Digest
    protected_paths: list[RelPath]
    policy_hash: Digest
    assistant_argv_digest: Digest
    degraded: list[str] = Field(default_factory=list)
    simulated: bool
    pubkey: str


class MarkerRead(Base):
    kind: Literal[Kind.marker_read] = Kind.marker_read
    peer_pid: int | None = None
    peer_exe: str | None = None
    path: Literal["/v1/token"] = "/v1/token"
    ua_digest: Digest | None = None
    # True only when the peer's process group was resolved AND differs from
    # the recorded run's pgid, at the moment of connection (not via later
    # polling, which a short-lived process can race past entirely). False
    # (the default) covers both "same group" and "couldn't be determined" —
    # this field only ever adds evidence, never asserts an escape it can't
    # back up with a direct observation.
    peer_escaped: bool = False


class OutboundPost(Base):
    kind: Literal[Kind.outbound_post] = Kind.outbound_post
    peer_pid: int | None = None
    peer_exe: str | None = None
    peer_escaped: bool = False
    dest: HostStr
    bytes: int
    body_sha256: Digest
    content_type: Literal["json", "form", "text", "binary", "other"]
    contains_marker: bool


class FsEvent(Base):
    kind: Literal[Kind.fs_event] = Kind.fs_event
    op: FsOp
    path: RelPath
    bytes: int | None = None
    sha256: Digest | None = None
    protected: bool


class ProcEvent(Base):
    kind: Literal[Kind.proc_event] = Kind.proc_event
    op: ProcOp
    pid: int
    ppid: int | None = None
    exe: str | None = None
    cmdline_digest: Digest | None = None


class AssistantClaim(Base):
    kind: Literal[Kind.assistant_claim] = Kind.assistant_claim
    source: Literal["session_log", "json_output"]
    tool: ClaimTool
    claimed_paths: list[RelPath] = Field(default_factory=list)
    claimed_hosts: list[HostStr] = Field(default_factory=list)
    claimed_count: int | None = None
    line_digest: Digest


class TailMeta(Base):
    kind: Literal[Kind.tail_meta] = Kind.tail_meta
    event: Literal["open", "reopen", "rotate", "parse_error", "truncate"]
    file: RelPath
    bytes_skipped: int = 0


class Finding(Base):
    kind: Literal[Kind.finding] = Kind.finding
    fkind: FindingKind
    severity: Severity
    evidence_seqs: list[int]
    score: float | None = None
    detector_version: str


class ActionResult(Base):
    kind: Literal[Kind.action_result] = Kind.action_result
    action: Literal["close_marker", "stop_pgroup", "sign_receipt"]
    finding_seq: int
    ok: bool
    latency_ms: int
    detail: Literal["term", "kill", "failed", "noop", "already_closed"] | None = None


class ClockWarning(Base):
    kind: Literal[Kind.clock_warning] = Kind.clock_warning
    delta_s: float


class RunEnd(Base):
    kind: Literal[Kind.run_end] = Kind.run_end
    reason: Literal["assistant_exit", "stopped", "interrupted", "timeout", "ledger_error"]
    exit_code: int | None = None
    records: int


# Same byte-stability concern as Receipt v0.2 below, but at the top level
# of an arbitrary record rather than nested inside `receipt.body`: adding
# `peer_escaped` to MarkerRead/OutboundPost changes their canonical bytes
# unless it's stripped back out when at its just-added default, for every
# record kind + field pair added after that kind's original schema froze.
_ADDITIVE_RECORD_FIELD_DEFAULTS: dict[tuple[str, str], Any] = {
    ("marker_read", "peer_escaped"): False,
    ("outbound_post", "peer_escaped"): False,
}


def strip_additive_record_field_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove a top-level additive field from an already-`model_dump`ed
    record payload when it's exactly at its just-added default and the
    payload's `kind` matches — restores the exact pre-addition canonical
    bytes for an old bundle. Mutates in place; also returns, for chaining.
    Sibling to `strip_receipt_body_v02_defaults` (nested, receipt-only)."""
    kind = payload.get("kind")
    for (record_kind, field), default in _ADDITIVE_RECORD_FIELD_DEFAULTS.items():
        if kind == record_kind and payload.get(field, default) == default:
            payload.pop(field, None)
    return payload


# Receipt v0.2 fields, keyed to their own just-added default value. A
# receipt signed/chained BEFORE these fields existed never had these keys
# in its canonicalized bytes at all; once parsed through the current
# schema, pydantic fills them in with these defaults, which would
# otherwise silently change the canonical JSON (and therefore both the
# Ed25519 signature and the hash-chain digest) recomputed over it for
# every pre-v0.2 receipt ever frozen. `strip_receipt_body_v02_defaults`
# removes a key only when it's exactly at this default, reproducing the
# original canonical payload byte-for-byte for an old receipt — while a
# receipt that genuinely sets any of these (real git-tree data, real
# coverage) keeps that field in the hashed/signed payload, so it's still
# cryptographically bound. Used by both `actions/receipt.py` (signature)
# and `ledger.py` (chain digest) so the two digest schemes can never
# silently diverge on this. See `docs/ARCHITECTURE.md`'s "Receipt v0.2 /
# CI gate" section.
_RECEIPT_BODY_V02_DEFAULTS: dict[str, Any] = {
    "git_commit_sha": None,
    "git_tree_digest": None,
    "changed_file_digests": {},
    "coverage": [],
}


def strip_receipt_body_v02_defaults(body_payload: dict[str, Any]) -> dict[str, Any]:
    """Remove any Receipt v0.2 field from an already-`model_dump`ed
    `ReceiptBody` payload when it's exactly at its just-added default.
    Mutates `body_payload` in place; also returns it, for chaining."""
    for key, default in _RECEIPT_BODY_V02_DEFAULTS.items():
        if body_payload.get(key, default) == default:
            body_payload.pop(key, None)
    return body_payload


class Watcher(StrEnum):
    """One entry in `ReceiptBody.coverage` — a watcher that was actually
    active for this run. A small, fixed vocabulary (like `FindingKind`),
    not free text: this is what makes "no finding" legible as "not seen by
    active sensors" rather than "nothing happened." See
    `ReceiptBody.coverage`'s own docstring."""

    fs = "fs"
    marker = "marker"
    sink = "sink"
    proc = "proc"


class ReceiptBody(BaseModel):
    """v0.2 adds four OPTIONAL, additive fields binding the receipt to a
    git tree (see module docstring: schema is an extension, never a
    breaking change — every existing construction call site and every
    pre-v0.2 bundle round-trips unmodified):

    - `git_commit_sha` / `git_tree_digest`: best-effort git-tree binding,
      `None` when the lab directory isn't inside a git repository (the
      common case — most lab directories are disposable tmp dirs). Never
      required, never fails a run to compute.
    - `changed_file_digests`: the per-file `{relative_path: sha256}` map
      that `git_tree_digest` is the canonical digest OF — so a verifier
      can check a single file's coverage without recomputing the whole
      tree digest. Snapshot semantics: every regular file present under
      the lab directory at receipt-signing time (excluding `.git/`), not
      a strict pre/post session diff — see `docs/ARCHITECTURE.md`'s
      "Receipt v0.2 / CI gate" section for why that's still an honest
      coverage statement for a lab directory that's fresh per session.
    - `coverage`: which watchers (`Watcher`) were active for this run —
      e.g. `record`/`record-muse` have all four; `record-claude` never
      includes `proc` (its `ProcWatcher` watches a placeholder process,
      not the real agent's process tree — see `claude_journal.py` /
      `cli.py`'s `record_claude` docstring).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    final_digest: Digest
    records: int
    findings: dict[str, int]
    stop_status: Literal["not_needed", "ok", "failed"]
    policy_hash: Digest
    signed_at: float
    pubkey: str
    git_commit_sha: GitSha | None = None
    git_tree_digest: Digest | None = None
    changed_file_digests: dict[RelPath, Digest] = Field(default_factory=dict)
    coverage: list[Watcher] = Field(default_factory=list)

    def canonical_payload(self) -> dict[str, Any]:
        """`model_dump(mode="json")` with any at-default Receipt v0.2
        field stripped (see `strip_receipt_body_v02_defaults`) — the
        exact bytes both the Ed25519 signature and the hash-chain digest
        are computed over. Always use this, never a raw `model_dump`,
        anywhere a `ReceiptBody` is signed, verified, or chain-digested."""
        return strip_receipt_body_v02_defaults(self.model_dump(mode="json"))


class Receipt(Base):
    kind: Literal[Kind.receipt] = Kind.receipt
    body: ReceiptBody
    sig: str  # base64 Ed25519 signature over canon(body)


class ReportStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    seq_refs: list[int]
    code: str
    severity: Severity


class Discrepancy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_seq: int
    record_seqs: list[int]
    code: str


class Report(Base):
    kind: Literal[Kind.report] = Kind.report
    model_id: str
    prompt_version: Digest
    analyst_status: Literal["ok", "offline", "schema_fail"]
    tool_calls: int
    summary_codes: list[str] = Field(default_factory=list)
    timeline: list[ReportStep] = Field(default_factory=list)
    reported_vs_recorded: list[Discrepancy] = Field(default_factory=list)
    confidence: float


Record = Annotated[
    Manifest
    | MarkerRead
    | OutboundPost
    | FsEvent
    | ProcEvent
    | AssistantClaim
    | TailMeta
    | Finding
    | ActionResult
    | ClockWarning
    | RunEnd
    | Receipt
    | Report,
    Field(discriminator="kind"),
]

__all__ = [
    "ActionResult",
    "AssistantClaim",
    "Base",
    "ClaimTool",
    "ClockWarning",
    "Digest",
    "Discrepancy",
    "Finding",
    "FindingKind",
    "FsEvent",
    "FsOp",
    "GitSha",
    "HostStr",
    "Kind",
    "Manifest",
    "MarkerRead",
    "OutboundPost",
    "ProcEvent",
    "ProcOp",
    "Receipt",
    "ReceiptBody",
    "Record",
    "RelPath",
    "Report",
    "ReportStep",
    "RunEnd",
    "Severity",
    "TailMeta",
    "Watcher",
    "strip_additive_record_field_defaults",
    "strip_receipt_body_v02_defaults",
]
