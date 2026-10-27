"""Integration test for `witness record-claude`'s orchestration.

Unlike `test_record_muse.py`, this test needs no external binary and is
never skipped: `record-claude` never spawns `claude` itself (see
`cli.py`'s `record_claude` docstring — the operator runs `claude` by hand;
this command only tails the resulting session log). So the test exercises
exactly what the command does in production — `_run_record` wired with
`tail_paths=[<a real session.jsonl>]` and `ClaudeCodeClaimParser`, behind a
no-op placeholder process standing in for the operator's separately
launched `claude` — against the real, committed, sanitized fixture.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from witness.bundle import build_bundle
from witness.claude_journal import ClaudeCodeClaimParser
from witness.cli import _run_record
from witness.config import RecordConfig

FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "claude_journal" / "success_session.txt"
)

pytestmark = pytest.mark.skipif(shutil.which("sleep") is None, reason="no `sleep` on PATH")


def test_record_claude_tails_real_fixture_end_to_end(tmp_path: Path) -> None:
    lab = tmp_path / "lab"
    runs_dir = tmp_path / "runs"
    session_log = tmp_path / "session.jsonl"
    shutil.copy(FIXTURE, session_log)

    config = RecordConfig(lab=lab, max_seconds=2.0)
    run_dir = _run_record(
        config,
        ["sleep", "2"],
        runs_dir,
        tail_paths=[session_log],
        tail_parser=ClaudeCodeClaimParser(),
    )

    bundle_path = run_dir / "bundle.jsonl"
    info = build_bundle(run_dir, bundle_path)
    assert info.receipt_ok is True
    assert info.records > 0

    # The real Write claim from the fixture must have made it into the
    # ledger/bundle as an assistant_claim record.
    import json

    claim_kinds = []
    with open(bundle_path) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("kind") == "assistant_claim":
                claim_kinds.append(rec["tool"])
    assert claim_kinds == ["write"]
