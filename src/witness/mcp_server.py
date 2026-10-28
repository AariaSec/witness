"""A local, read-only MCP server exposing `witness verify`'s already-
tested logic as tools a coding agent (Muse Code, Claude Code, any MCP
client) can call directly in conversation — "ask the agent to check this
receipt" instead of running the CLI by hand.

Deliberately NOT a hosted connector: stdio transport only, no auth, no
public distribution, no platform review needed — run it locally, wire it
into an agent's own `mcpServers` config, done. See README.md's "Use it
from a coding agent" section for the exact config snippet and a live demo
script.

Deliberately read-only and content-free, same RULE-1-analog boundary as
everything else in this project: every tool here wraps an EXISTING,
already-unit-tested function in `bundle.py`/`cli.py` — no new detection
logic, no write path, nothing that could mutate a bundle or a receipt.
Every return value is counts/enums/paths/digests, never raw file content.

Why this exists for the hackathon specifically: MCP connectors are a live
interest point right now, and this is a genuinely bounded, real
capability to demonstrate it with — not a toy "hello world" tool, an
actual interface onto the project's real, signed, chain-verified data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from witness.bundle import BundleChainInvalid, BundleQuarantined, validate_bundle
from witness.cli import _resolve_analyst_client, _tree_check_report
from witness.ledger import read_ledger
from witness.models import Finding, Kind, Receipt

mcp = MCPServer(
    name="witness",
    title="witness — independent agent-session recorder",
    instructions=(
        "Read-only tools over a witness bundle.jsonl: a content-free, "
        "chain-verified, Ed25519-signed record of what a coding agent "
        "actually did (files, processes, network), independent of the "
        "agent's own self-report. Never returns raw prompt/response text "
        "— only counts, enums, paths, and digests."
    ),
)


@mcp.tool(
    description=(
        "Re-verify a witness bundle.jsonl: hash chain, key whitelist, and "
        "Ed25519 receipt signature, plus the built-in policy check (does "
        "any stop-severity finding make this a merge-gate FAIL). Mirrors "
        "`witness verify` exactly — same checks, same meaning."
    )
)
def witness_verify_bundle(bundle_path: str) -> dict[str, Any]:
    try:
        info = validate_bundle(Path(bundle_path))
    except BundleQuarantined as exc:
        return {"ok": False, "reason": "leak_scan_violation", "violation_count": len(exc.violations)}
    except BundleChainInvalid as exc:
        return {"ok": False, "reason": "chain_invalid", "first_bad_seq": exc.first_bad_seq}
    except FileNotFoundError:
        return {"ok": False, "reason": "file_not_found", "bundle_path": bundle_path}

    if info.receipt_status != "ok":
        return {"ok": False, "reason": f"receipt_{info.receipt_status}"}

    return {
        "ok": True,
        "run_id": info.run_id,
        "records": info.records,
        "findings": info.findings,
        "receipt_ok": info.receipt_ok,
        "policy": "PASS" if info.stop_findings == 0 else "FAIL",
        "stop_findings": info.stop_findings,
    }


@mcp.tool(
    description=(
        "List every finding in a witness bundle.jsonl with its severity "
        "(info/warn/stop), evidence seqs, and detector score if any. "
        "Content-free: a finding is a kind + severity + seq numbers "
        "pointing back to other records, never the underlying evidence "
        "text."
    )
)
def witness_list_findings(bundle_path: str) -> list[dict[str, Any]]:
    records = read_ledger(Path(bundle_path))
    out: list[dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, Finding):
            continue
        out.append(
            {
                "seq": rec.seq,
                "fkind": rec.fkind.value,
                "severity": rec.severity.value,
                "evidence_seqs": rec.evidence_seqs,
                "score": rec.score,
                "detector_version": rec.detector_version,
            }
        )
    return out


@mcp.tool(
    description=(
        "Cross-check a directory against a bundle's receipt-attested git "
        "tree coverage (Receipt v0.2's body.changed_file_digests). Every "
        "file actually present under tree_dir is classified covered "
        "(digest matches the receipt), modified (path known, digest "
        "differs), or unattested (no covering receipt entry at all). "
        "Mirrors `witness verify --against-tree` exactly."
    )
)
def witness_check_tree_coverage(bundle_path: str, tree_dir: str) -> dict[str, Any]:
    records = read_ledger(Path(bundle_path))
    receipt = next((r for r in records if r.kind == Kind.receipt), None)
    if receipt is None or not isinstance(receipt, Receipt):
        return {"ok": False, "reason": "no_receipt_present"}

    covered, modified, unattested, details = _tree_check_report(
        receipt.body.changed_file_digests, Path(tree_dir)
    )
    return {
        "ok": True,
        "covered": covered,
        "modified": modified,
        "unattested": unattested,
        "details": [{"status": status, "path": path} for status, path in details],
    }


@mcp.tool(
    description=(
        "Produce an advisory narrative Report for a witness bundle.jsonl: "
        "a timeline of findings in canonical codes, reported-vs-recorded "
        "discrepancies, and a confidence score. `provider` is "
        "'offline' (default: zero API key, zero network call, a "
        "deterministic template), 'baseten' (Meta open-weight Muse Spark "
        "Open), or 'meta' (Meta's own first-party hosted Model API). A "
        "live provider that's unavailable or fails schema validation "
        "falls back to the offline template automatically — this call "
        "never raises on a bad or missing key. Advisory only: this report "
        "never affects witness_verify_bundle's pass/fail policy decision, "
        "same as `witness verify --with-analyst`."
    )
)
def witness_analyze_bundle(bundle_path: str, provider: str = "offline") -> dict[str, Any]:
    from witness.analyst.run import analyze

    client = None if provider == "offline" else _resolve_analyst_client(provider)
    report = analyze(Path(bundle_path), client=client)
    return {
        "model_id": report.model_id,
        "analyst_status": report.analyst_status,
        "confidence": report.confidence,
        "summary_codes": report.summary_codes,
        "timeline": [step.model_dump(mode="json") for step in report.timeline],
        "reported_vs_recorded": [d.model_dump(mode="json") for d in report.reported_vs_recorded],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
