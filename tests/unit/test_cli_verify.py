"""`witness verify` — the extended CLI command (Receipt v0.2 / CI gate).

Covers the full adversarial matrix the GitHub Action gate depends on:
byte-flip, wrong key, truncated/reordered chain, missing receipt, a file
modified after the session, and a file never in the receipt at all —
every one of these must produce a clear, distinct, non-zero exit, never
a silent pass. Also exercises the new `--against-tree` coverage check and
the built-in policy check (stop-severity finding -> FAIL) against both
synthetic fixtures and the real, committed bundles under `runs/frozen/`
and `corpus/benign/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from witness.actions.receipt import Signer
from witness.bundle import build_bundle
from witness.cli import (
    VERIFY_EXIT_CHAIN_INVALID,
    VERIFY_EXIT_LEAK_VIOLATION,
    VERIFY_EXIT_OK,
    VERIFY_EXIT_POSTURE_FAIL,
    VERIFY_EXIT_RECEIPT_INVALID,
    app,
)
from witness.ledger import Ledger, _record_digest  # _record_digest: internal, test-only reuse
from witness.models import Finding, Manifest, Receipt, ReceiptBody, Severity

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_MUSE_BUNDLE = (
    _REPO_ROOT
    / "runs"
    / "frozen"
    / "muse-real-agent-proof-20261026-185538-7c88"
    / "bundle.jsonl"
)
_BENIGN_CORPUS_BUNDLE = _REPO_ROOT / "corpus" / "benign" / "b01.jsonl"
_STOP_FINDING_BUNDLE = (
    _REPO_ROOT / "runs" / "frozen" / "analyst-live-proof-20261026-145221-6150" / "bundle.jsonl"
)


def _manifest() -> Manifest:
    return Manifest(
        bundle_schema="1.0",
        witness_version="0.1.0",
        run_id="r1",
        platform="darwin",
        marker_port=1,
        sink_port=2,
        lab_root_digest="0" * 64,
        protected_paths=["protected"],
        policy_hash="0" * 64,
        assistant_argv_digest="0" * 64,
        simulated=True,
        pubkey="abc",
    )


def _build_bundle(
    tmp_path: Path,
    *,
    with_stop_finding: bool = False,
    changed_file_digests: dict[str, str] | None = None,
    with_receipt: bool = True,
) -> Path:
    """Build one small, real, chain-verified, signed bundle.jsonl under
    `tmp_path`, with optional knobs for the adversarial/posture tests
    below. Uses the real `Signer`/`Ledger` — not a hand-faked digest."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ledger = Ledger(run_dir / "ledger.jsonl")
    ledger.append(_manifest())

    if with_stop_finding:
        ledger.append(
            Finding(
                fkind="protected_write",
                severity=Severity.stop,
                evidence_seqs=[0],
                detector_version="1.0",
            )
        )

    if with_receipt:
        signer = Signer.load_or_create(tmp_path / "keys")
        body = ReceiptBody(
            run_id="r1",
            final_digest=ledger.final_digest or "0" * 64,
            records=ledger.record_count,
            findings={"protected_write": 1} if with_stop_finding else {},
            stop_status="ok" if with_stop_finding else "not_needed",
            policy_hash="0" * 64,
            signed_at=1.0,
            pubkey=signer.public_key_b64,
            changed_file_digests=changed_file_digests or {},
        )
        receipt = signer.sign(body)
        ledger.append(receipt)

    ledger.close()
    out = run_dir / "bundle.jsonl"
    build_bundle(run_dir, out)
    return out


def _read_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_lines(path: Path, lines: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")


def _tamper_receipt_body_keep_chain_intact(
    lines: list[dict[str, object]], key: str, value: object
) -> None:
    """Mutate `receipt.body[key] = value` and recompute the record's OWN
    hash-chain `digest` to match — isolating the test to "does the
    Ed25519 SIGNATURE catch this," since the hash chain alone (no
    external signing key) can never catch a self-consistent tamper. This
    is the realistic attack this receipt scheme defends against: an
    attacker who controls the whole ledger file but not the private key."""
    idx = next(i for i, line in enumerate(lines) if line["kind"] == "receipt")
    prev = lines[idx]["prev"]
    body = lines[idx]["body"]
    assert isinstance(body, dict)
    body[key] = value
    draft = Receipt.model_validate({**lines[idx], "digest": None})
    lines[idx]["digest"] = _record_digest(draft, prev)  # type: ignore[arg-type]


# --- Happy path -----------------------------------------------------------


def test_verify_happy_path_exits_ok(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_OK, result.output
    assert "receipt_ok=True" in result.output
    assert "policy: PASS" in result.output


# --- Adversarial matrix -----------------------------------------------------


def test_verify_byte_flipped_signed_body_is_invalid(tmp_path: Path) -> None:
    """A tamper that keeps the hash chain self-consistent (an attacker
    who controls the whole ledger file) must still be caught — by the
    Ed25519 signature, which they can't forge without the private key."""
    bundle = _build_bundle(tmp_path)
    lines = _read_lines(bundle)
    original_records = lines[next(i for i, line in enumerate(lines) if line["kind"] == "receipt")][
        "body"
    ]["records"]  # type: ignore[index]
    _tamper_receipt_body_keep_chain_intact(lines, "records", original_records + 1)
    _write_lines(bundle, lines)

    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_RECEIPT_INVALID
    assert "signature verification failed" in result.output


def test_verify_wrong_public_key_is_invalid(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    lines = _read_lines(bundle)
    other_signer = Signer.load_or_create(tmp_path / "other_keys")
    # Signature now verifies against the WRONG key, even though the chain
    # itself stays internally consistent.
    _tamper_receipt_body_keep_chain_intact(lines, "pubkey", other_signer.public_key_b64)
    _write_lines(bundle, lines)

    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_RECEIPT_INVALID
    assert "signature verification failed" in result.output


def test_verify_truncated_chain_is_invalid(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, with_stop_finding=True)
    lines = _read_lines(bundle)
    assert len(lines) >= 3
    del lines[1]  # drop a MIDDLE record -> every later prev-link breaks
    _write_lines(bundle, lines)

    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_CHAIN_INVALID
    assert "hash chain broken" in result.output


def test_verify_reordered_records_is_invalid(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, with_stop_finding=True)
    lines = _read_lines(bundle)
    assert len(lines) >= 3
    lines[0], lines[1] = lines[1], lines[0]  # swap two records out of order
    _write_lines(bundle, lines)

    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_CHAIN_INVALID


def test_verify_missing_receipt_is_a_clear_distinct_error_never_a_silent_pass(
    tmp_path: Path,
) -> None:
    bundle = _build_bundle(tmp_path, with_receipt=False)
    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_RECEIPT_INVALID
    assert result.exit_code != VERIFY_EXIT_OK
    assert "no receipt record present" in result.output


def test_verify_tree_check_reports_modified_file(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("original")
    from witness.gittree import compute_file_digests

    digests = compute_file_digests(tree)
    bundle = _build_bundle(tmp_path, changed_file_digests=digests)

    # Simulate a post-session edit.
    (tree / "a.py").write_text("tampered after the session")

    result = runner.invoke(app, ["verify", str(bundle), "--against-tree", str(tree)])
    assert result.exit_code == VERIFY_EXIT_POSTURE_FAIL
    assert "modified: a.py" in result.output
    assert "modified=1" in result.output


def test_verify_tree_check_reports_unattested_file(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "known.py").write_text("known")
    from witness.gittree import compute_file_digests

    digests = compute_file_digests(tree)
    bundle = _build_bundle(tmp_path, changed_file_digests=digests)

    # A file nobody ever attested to — added after the receipt was signed,
    # or just never part of this session.
    (tree / "surprise.py").write_text("nobody attested to this")

    result = runner.invoke(app, ["verify", str(bundle), "--against-tree", str(tree)])
    assert result.exit_code == VERIFY_EXIT_POSTURE_FAIL
    assert "unattested: surprise.py" in result.output
    assert "unattested=1" in result.output


def test_verify_tree_check_all_covered_exits_ok(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_text("unchanged")
    from witness.gittree import compute_file_digests

    digests = compute_file_digests(tree)
    bundle = _build_bundle(tmp_path, changed_file_digests=digests)

    result = runner.invoke(app, ["verify", str(bundle), "--against-tree", str(tree)])
    assert result.exit_code == VERIFY_EXIT_OK
    assert "covered=1 modified=0 unattested=0" in result.output


# --- Policy check (stop-severity finding -> FAIL) --------------------------


def test_verify_policy_fails_on_stop_severity_finding(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, with_stop_finding=True)
    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_POSTURE_FAIL
    assert "policy: FAIL (stop findings: 1)" in result.output


def test_verify_policy_passes_with_no_stop_finding(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, with_stop_finding=False)
    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_OK
    assert "policy: PASS (stop findings: 0)" in result.output


# --- Leak-scan / whitelist violation ----------------------------------------


def test_verify_disallowed_key_is_a_leak_violation(tmp_path: Path) -> None:
    """`findings` is typed `dict[str, int]` — pydantic's `extra=forbid`
    doesn't constrain its KEYS (unlike a schema field name), so a bogus
    key here passes pydantic validation and must be caught by the
    independent whitelist scan instead (same mechanism
    `test_findings_dynamic_keys_are_whitelisted` in test_leakscan.py
    exercises directly)."""
    bundle = _build_bundle(tmp_path)
    lines = _read_lines(bundle)
    _tamper_receipt_body_keep_chain_intact(lines, "findings", {"not_a_real_finding_kind": 1})
    _write_lines(bundle, lines)

    result = runner.invoke(app, ["verify", str(bundle)])
    assert result.exit_code == VERIFY_EXIT_LEAK_VIOLATION


# --- Real, committed bundles (not only synthetic) --------------------------


def test_verify_real_muse_bundle_exits_ok() -> None:
    result = runner.invoke(app, ["verify", str(_REAL_MUSE_BUNDLE)])
    assert result.exit_code == VERIFY_EXIT_OK, result.output


def test_verify_real_benign_corpus_bundle_exits_ok() -> None:
    result = runner.invoke(app, ["verify", str(_BENIGN_CORPUS_BUNDLE)])
    assert result.exit_code == VERIFY_EXIT_OK, result.output


def test_verify_real_bundle_with_stop_finding_fails_policy() -> None:
    result = runner.invoke(app, ["verify", str(_STOP_FINDING_BUNDLE)])
    assert result.exit_code == VERIFY_EXIT_POSTURE_FAIL
    assert "policy: FAIL" in result.output


def test_verify_real_muse_bundle_against_tree_reports_unattested_without_crashing(
    tmp_path: Path,
) -> None:
    """A real pre-v0.2 bundle has an empty `changed_file_digests` — every
    file in an arbitrary `--against-tree` directory must read as
    `unattested` (an honest "this bundle never attested to a git tree"),
    not a crash and not a silent pass."""
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "some_file.py").write_text("irrelevant content")

    result = runner.invoke(
        app, ["verify", str(_REAL_MUSE_BUNDLE), "--against-tree", str(tree)]
    )
    assert result.exit_code == VERIFY_EXIT_POSTURE_FAIL
    assert "unattested: some_file.py" in result.output


@pytest.mark.parametrize("bundle", [_REAL_MUSE_BUNDLE, _BENIGN_CORPUS_BUNDLE])
def test_subprocess_invocation_matches_library_call_exit_code(bundle: Path) -> None:
    """A real subprocess invocation (what the GitHub Action actually
    shells out to) must agree with the in-process `CliRunner` result."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "witness.cli", "verify", str(bundle)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == VERIFY_EXIT_OK, result.stderr


def test_with_analyst_falls_back_to_offline_template_without_a_key(monkeypatch) -> None:
    """`--with-analyst` must never change the exit code or crash when no
    Baseten key is available (the exact CI case before a secret is
    configured) — it degrades to the same offline template `analyze()`
    already guarantees, same as calling it with `client=None` directly.
    Patches `_resolve_analyst_client` itself (rather than poking at
    `BasetenClient`'s internals) so this test is deterministic and never
    makes a real network call, regardless of what's on this machine."""
    monkeypatch.setattr("witness.cli._resolve_analyst_client", lambda *a, **k: None)

    result = runner.invoke(app, ["verify", str(_REAL_MUSE_BUNDLE), "--with-analyst"])

    assert result.exit_code == VERIFY_EXIT_OK
    assert "analyst: status=offline" in result.output
    assert "confidence=" in result.output


def test_with_analyst_never_changes_exit_code_on_a_stop_finding(monkeypatch) -> None:
    """Same guarantee on the FAIL path: the analyst note is printed, but
    the exit code still comes entirely from the policy/chain/signature
    checks, never from the analyst call succeeding or failing."""
    monkeypatch.setattr("witness.cli._resolve_analyst_client", lambda *a, **k: None)

    result = runner.invoke(app, ["verify", str(_STOP_FINDING_BUNDLE), "--with-analyst"])

    assert result.exit_code == VERIFY_EXIT_POSTURE_FAIL
    assert "analyst: status=offline" in result.output


def test_analyst_provider_flag_is_passed_through_to_resolver(monkeypatch) -> None:
    """--analyst-provider fireworks must reach _resolve_analyst_client,
    not silently stay on the baseten default."""
    seen: list[str] = []
    monkeypatch.setattr(
        "witness.cli._resolve_analyst_client", lambda provider: (seen.append(provider), None)[1]
    )

    result = runner.invoke(
        app, ["verify", str(_REAL_MUSE_BUNDLE), "--with-analyst", "--analyst-provider", "fireworks"]
    )

    assert result.exit_code == VERIFY_EXIT_OK
    assert seen == ["fireworks"]


def test_analyst_provider_defaults_to_baseten(monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        "witness.cli._resolve_analyst_client", lambda provider: (seen.append(provider), None)[1]
    )

    runner.invoke(app, ["verify", str(_REAL_MUSE_BUNDLE), "--with-analyst"])

    assert seen == ["baseten"]


def test_resolve_analyst_client_unknown_provider_returns_none() -> None:
    from witness.cli import _resolve_analyst_client

    assert _resolve_analyst_client("not-a-real-provider") is None


def test_fireworks_client_missing_key_file_raises(tmp_path) -> None:
    """Same guarantee BasetenClient's key-file read already has, for the
    second provider: a missing key file is a clean LLMClientError, not an
    unhandled OSError."""
    from witness.analyst.client import FireworksClient, LLMClientError

    with pytest.raises(LLMClientError, match="no Fireworks key"):
        FireworksClient(key_path=tmp_path / "no-such-key-file")


def test_baseten_client_missing_key_file_raises(tmp_path) -> None:
    """Was previously untested at this level (only exercised live) --
    closing the gap while adding FireworksClient's equivalent above."""
    from witness.analyst.client import BasetenClient, LLMClientError

    with pytest.raises(LLMClientError, match="no Baseten key"):
        BasetenClient(key_path=tmp_path / "no-such-key-file")
