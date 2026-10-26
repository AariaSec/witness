"""Session log / JSON output follower → `AssistantClaim` records.

The assistant's own session log and JSON output are the one place this
system reads data the assistant produced. Nothing here ever stores a raw
line: every line is reduced, on a best-effort parse, to a `ClaimTool`
enum, a small bounded list of claimed paths/hosts, an optional count, and
a `line_digest` (sha256 of the raw line bytes). On any parse failure the
raw bytes are discarded and only a byte count survives, via `TailMeta`.

Format note: the real Muse Code session-journal schema is undocumented
(see final-plan audit); this module defines its own simple, content-free,
line-delimited JSON claim format (`{"tool": ..., "paths": [...],
"hosts": [...], "count": ...}`) that `demo/sim_agent.py` writes to and
this module reads from. Parsing never raises — invariant exercised by
`tests/property/test_tailer_fuzz.py`.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from witness.canon import sha256_hex
from witness.models import AssistantClaim, ClaimTool, TailMeta

_POLL_S = 0.1
_MAX_LINE = 2 * 2**20  # 2 MB hard cap; longer lines are truncated, never raise


def _claim_from_obj(obj: object, source: str, line_digest: str) -> AssistantClaim | None:
    if not isinstance(obj, dict):
        return None
    tool_raw = obj.get("tool")
    if not isinstance(tool_raw, str):
        return None
    try:
        tool = ClaimTool(tool_raw)
    except ValueError:
        return None

    paths = obj.get("paths") or []
    hosts = obj.get("hosts") or []
    count = obj.get("count")

    if not isinstance(paths, list):
        paths = []
    if not isinstance(hosts, list):
        hosts = []
    if not isinstance(count, int):
        count = None

    clean_paths = [str(p)[:256] for p in paths if isinstance(p, (str, int, float))][:50]
    clean_hosts = [str(h)[:255] for h in hosts if isinstance(h, (str, int, float))][:50]

    try:
        return AssistantClaim(
            source=source,  # type: ignore[arg-type]
            tool=tool,
            claimed_paths=clean_paths,
            claimed_hosts=clean_hosts,
            claimed_count=count,
            line_digest=line_digest,
        )
    except ValidationError:
        return None


def parse_session_line(line: bytes) -> AssistantClaim | None:
    """Pure parse of one session-log line. Never raises."""
    try:
        line = line.rstrip(b"\r\n")
        if not line.strip():
            return None
        digest = sha256_hex(line[:_MAX_LINE])
        obj = json.loads(line.decode("utf-8", errors="strict"))
        return _claim_from_obj(obj, "session_log", digest)
    except Exception:
        return None


def parse_json_output(obj: object) -> list[AssistantClaim]:
    """Pure parse of a JSON-output document shaped
    `{"actions": [{"tool": ..., "paths": [...], "hosts": [...]}]}`.
    Never raises."""
    claims: list[AssistantClaim] = []
    try:
        if not isinstance(obj, dict):
            return claims
        actions = obj.get("actions")
        if not isinstance(actions, list):
            return claims
        for action in actions:
            try:
                raw = json.dumps(action, sort_keys=True, default=str).encode("utf-8")
            except Exception:
                continue
            digest = sha256_hex(raw[:_MAX_LINE])
            claim = _claim_from_obj(action, "json_output", digest)
            if claim is not None:
                claims.append(claim)
    except Exception:
        return claims
    return claims


class ClaimParser(Protocol):
    def parse_line(self, line: bytes, source: str) -> AssistantClaim | TailMeta | None: ...


class DefaultClaimParser:
    """Line-delimited JSON claim parser shared by both `.log` and `.json`
    tailed files (see module docstring for the format)."""

    def parse_line(self, line: bytes, source: str) -> AssistantClaim | TailMeta | None:
        line = line.rstrip(b"\r\n")
        if not line.strip():
            return None
        if len(line) > _MAX_LINE:
            return TailMeta(event="parse_error", file="", bytes_skipped=len(line))
        try:
            digest = sha256_hex(line)
            obj = json.loads(line.decode("utf-8", errors="strict"))
        except Exception:
            return TailMeta(event="parse_error", file="", bytes_skipped=len(line))
        claim = _claim_from_obj(obj, source, digest)
        if claim is None:
            return TailMeta(event="parse_error", file="", bytes_skipped=len(line))
        return claim


class _FileState:
    __slots__ = ("buffer", "inode", "offset")

    def __init__(self) -> None:
        self.inode: int | None = None
        self.offset: int = 0
        self.buffer: bytes = b""


class Tailer:
    """`EventSource` following a fixed list of files by inode, reopening on
    rotation/truncation, emitting `AssistantClaim`/`TailMeta` records."""

    def __init__(self, files: list[Path], parser: ClaimParser | None = None) -> None:
        self._files = [Path(f) for f in files]
        self._parser = parser or DefaultClaimParser()
        self._states: dict[Path, _FileState] = {f: _FileState() for f in self._files}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._emit: Callable[[BaseModel], None] | None = None

    def _source_for(self, f: Path) -> str:
        return "json_output" if f.suffix == ".json" else "session_log"

    def _emit_rec(self, rec: BaseModel, file_rel: str) -> None:
        if isinstance(rec, TailMeta) and rec.file == "":
            rec = rec.model_copy(update={"file": file_rel})
        if self._emit is not None:
            self._emit(rec)

    def _poll_file(self, f: Path) -> None:
        state = self._states[f]
        file_rel = f.name[:256]
        try:
            st = f.stat()
        except FileNotFoundError:
            return

        inode = st.st_ino
        if state.inode is None:
            state.inode = inode
            self._emit_rec(TailMeta(event="open", file=file_rel, bytes_skipped=0), file_rel)
        elif inode != state.inode:
            state.inode = inode
            state.offset = 0
            state.buffer = b""
            self._emit_rec(TailMeta(event="rotate", file=file_rel, bytes_skipped=0), file_rel)
        elif st.st_size < state.offset:
            skipped = state.offset
            state.offset = 0
            state.buffer = b""
            self._emit_rec(
                TailMeta(event="truncate", file=file_rel, bytes_skipped=skipped), file_rel
            )

        try:
            with open(f, "rb") as fh:
                fh.seek(state.offset)
                chunk = fh.read()
                state.offset = fh.tell()
        except OSError:
            return

        if not chunk:
            return

        data = state.buffer + chunk
        lines = data.split(b"\n")
        state.buffer = lines.pop()  # last element: partial line (no trailing \n)

        source = self._source_for(f)
        for line in lines:
            if not line.strip():
                continue
            rec = self._parser.parse_line(line, source)
            if rec is not None:
                self._emit_rec(rec, file_rel)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            for f in self._files:
                self._poll_file(f)
            self._stop_event.wait(_POLL_S)

    def start(self, emit: Callable[[BaseModel], None]) -> None:
        self._emit = emit
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        # The background loop's `wait()` returns immediately once
        # `_stop_event` is set, which can skip the tick that would have
        # caught a write landing between the last poll and this call (a
        # short-lived assistant process can exit before the next 0.1s
        # tick). The thread has fully stopped by now (joined above), so
        # this is safe to run single-threaded.
        for f in self._files:
            self._poll_file(f)


__all__ = [
    "ClaimParser",
    "DefaultClaimParser",
    "Tailer",
    "parse_json_output",
    "parse_session_line",
]
