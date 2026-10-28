"""witness.mcp_server: every tool wraps an existing, already-tested
function -- these tests check the MCP-shaped wrapper layer itself
(argument handling, return shape, error paths), not the underlying
verify/findings/tree-check logic a second time (that's covered in
test_bundle.py/test_cli_verify.py already).

`mcp` is an optional extra (`pip install -e ".[mcp]"`) -- skip this whole
file rather than fail collection if it isn't installed, so a clean
checkout without that extra still passes the rest of the gate.
"""

from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from pathlib import Path  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_BUNDLE = REPO_ROOT / "runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl"
_STOP_FINDING_BUNDLE = REPO_ROOT / "console/public/bundles/demo-red.jsonl"


def test_verify_bundle_on_a_real_passing_bundle() -> None:
    from witness.mcp_server import witness_verify_bundle

    result = witness_verify_bundle(str(_REAL_BUNDLE))

    assert result["ok"] is True
    assert result["policy"] == "PASS"
    assert result["stop_findings"] == 0
    assert result["receipt_ok"] is True
    assert "marker_read" in result["findings"]


def test_verify_bundle_on_a_real_failing_bundle() -> None:
    from witness.mcp_server import witness_verify_bundle

    result = witness_verify_bundle(str(_STOP_FINDING_BUNDLE))

    assert result["ok"] is True  # the bundle itself verifies cleanly...
    assert result["policy"] == "FAIL"  # ...but the policy check is a real FAIL
    assert result["stop_findings"] >= 1


def test_verify_bundle_missing_file_returns_error_not_exception() -> None:
    from witness.mcp_server import witness_verify_bundle

    result = witness_verify_bundle("/no/such/bundle.jsonl")

    assert result["ok"] is False
    assert result["reason"] == "file_not_found"


def test_list_findings_matches_verify_bundles_finding_counts() -> None:
    from witness.mcp_server import witness_list_findings, witness_verify_bundle

    findings = witness_list_findings(str(_REAL_BUNDLE))
    counts = witness_verify_bundle(str(_REAL_BUNDLE))["findings"]

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f["fkind"]] = by_kind.get(f["fkind"], 0) + 1
    assert by_kind == counts


def test_list_findings_never_includes_raw_content_keys() -> None:
    """Content-free discipline: every finding dict here must only ever
    have the fixed, documented key set -- never a stray field a future
    change might accidentally add with real content in it."""
    from witness.mcp_server import witness_list_findings

    findings = witness_list_findings(str(_REAL_BUNDLE))
    allowed_keys = {"seq", "fkind", "severity", "evidence_seqs", "score", "detector_version"}
    for f in findings:
        assert set(f.keys()) <= allowed_keys


def test_check_tree_coverage_on_a_bundle_with_no_receipt_git_binding() -> None:
    """The real flagship bundles predate (or were recorded outside) a git
    tree, so every present file is correctly 'unattested', not an error."""
    from witness.mcp_server import witness_check_tree_coverage

    result = witness_check_tree_coverage(str(_REAL_BUNDLE), str(REPO_ROOT / "src/witness"))

    assert result["ok"] is True
    assert result["covered"] == 0
    assert result["unattested"] > 0
    assert all(d["status"] == "unattested" for d in result["details"])
