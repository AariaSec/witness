"""`witness watch` -- live/replay terminal rendering, the third interaction
surface alongside the web console (browser) and the MCP server (agent).
This one is for a human operator watching a session happen in their own
terminal, in real time or replayed at recorded/accelerated speed.

Pure, testable line-formatting lives here: `line_for` maps ONE bundle
record to ONE line of rich markup text. Content-free, same rule as every
other surface in this project -- every field used below is already a
digest/enum/count/path on the model (`models.py`); this module never
reads or prints raw prompt/response text, and never invents a new field.

The CLI command (`cli.py`'s `watch`) owns the I/O: tailing a live
`ledger.jsonl` (via the existing `_RecordAdapter` line-parser in
`ledger.py`, not a second parsing mechanism) or replaying a finished
`bundle.jsonl` at real `ts_mono`-delta pacing (optionally accelerated by
`--speed`).
"""

from __future__ import annotations

from witness.models import (
    ActionResult,
    AssistantClaim,
    ClockWarning,
    Finding,
    FsEvent,
    Manifest,
    MarkerRead,
    OutboundPost,
    ProcEvent,
    Receipt,
    Record,
    RunEnd,
    Severity,
    TailMeta,
)

_SEV_STYLE: dict[Severity, str] = {
    Severity.stop: "bold red",
    Severity.warn: "bold yellow",
    Severity.info: "bold blue",
}


def line_for(rec: Record) -> str:
    """One line of rich console markup for a single bundle record.

    Every branch below reads only fields already on the model -- never
    raw prompt/response text, never a synthesized value. Unknown/未-
    covered kinds (e.g. `report`) fall through to a generic line using
    only the record's own discriminator, so this never raises on a
    schema addition it hasn't been updated for yet.
    """
    ts = f"[dim]{rec.ts_mono:8.3f}s[/dim]"
    seq = f"[dim]#{rec.seq}[/dim]"

    if isinstance(rec, Manifest):
        sim = " [yellow](simulated)[/yellow]" if rec.simulated else ""
        return f"{ts} {seq} [bold]manifest[/bold] run={rec.run_id}{sim}"
    if isinstance(rec, MarkerRead):
        flag = " [bold red](escaped peer)[/bold red]" if rec.peer_escaped else ""
        return f"{ts} {seq} [cyan]marker_read[/cyan] pid={rec.peer_pid}{flag}"
    if isinstance(rec, OutboundPost):
        tag = "[bold red]outbound_post · contains_marker[/bold red]" if rec.contains_marker else "outbound_post"
        return f"{ts} {seq} {tag} dest={rec.dest} bytes={rec.bytes}"
    if isinstance(rec, FsEvent):
        tag = f"[bold red]fs_event:{rec.op} · contains_marker[/bold red]" if rec.contains_marker else f"fs_event:{rec.op}"
        prot = " [yellow](protected)[/yellow]" if rec.protected else ""
        return f"{ts} {seq} {tag} {rec.path}{prot}"
    if isinstance(rec, ProcEvent):
        return f"{ts} {seq} proc_event:{rec.op.value} pid={rec.pid} ppid={rec.ppid}"
    if isinstance(rec, AssistantClaim):
        return f"{ts} {seq} [magenta]assistant_claim[/magenta] tool={rec.tool.value} count={rec.claimed_count}"
    if isinstance(rec, TailMeta):
        return f"{ts} {seq} [dim]tail_meta:{rec.event}[/dim]"
    if isinstance(rec, Finding):
        style = _SEV_STYLE[rec.severity]
        return f"{ts} {seq} [{style}]{rec.severity.value.upper()}[/{style}] finding={rec.fkind.value} evidence={rec.evidence_seqs}"
    if isinstance(rec, ActionResult):
        status = "[green]ok[/green]" if rec.ok else "[bold red]FAILED[/bold red]"
        return f"{ts} {seq} action={rec.action} {status} {rec.latency_ms}ms"
    if isinstance(rec, ClockWarning):
        return f"{ts} {seq} [yellow]clock_warning[/yellow] delta={rec.delta_s}s"
    if isinstance(rec, RunEnd):
        return f"{ts} {seq} [bold]run_end[/bold] reason={rec.reason}"
    if isinstance(rec, Receipt):
        return f"{ts} {seq} [bold green]receipt signed[/bold green] key={rec.body.pubkey[:10]}… stop={rec.body.stop_status}"
    return f"{ts} {seq} {rec.kind.value}"


__all__ = ["line_for"]
