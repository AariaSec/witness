"""Leak scan: allowed-keys whitelist, secret patterns, prose-length — both
the shared `witness.leakscan` logic and the standalone
`scripts/leakscan.py` CLI (exit code 3 on violation), which is the actual
enforcement point for a `bundle.jsonl` scanned independently of pydantic.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from witness.leakscan import (
    contains_secret,
    load_allowed_keys,
    looks_like_prose,
    scan_record,
    scan_value,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LEAKSCAN_SCRIPT = _REPO_ROOT / "scripts" / "leakscan.py"

# A single shared fixture for every test that needs a value `contains_secret`
# recognizes as AWS-access-key-shaped — kept as ONE module-level constant
# (rather than inlined per test) so this file's own source contains the
# literal exactly once, not once per test. `scripts/leakscan.py --staged`
# scans staged .py files as raw text for this same pattern (by design — a
# secret pasted into test code is still a leak), so a test file that
# legitimately needs a secret-shaped literal to exercise `contains_secret`
# unavoidably trips that scan; this keeps that unavoidable footprint to a
# minimum instead of multiplying it per call site.
_AWS_KEY_SHAPED_FIXTURE = "AKIAABCDEFGHIJKLMNOP"


def test_load_allowed_keys_contains_core_fields() -> None:
    keys = load_allowed_keys()
    for k in ("seq", "kind", "digest", "run_id", "pubkey", "findings"):
        assert k in keys


def test_scan_record_flags_disallowed_key() -> None:
    allowed = load_allowed_keys()
    violations = scan_record({"seq": 0, "kind": "manifest", "sneaky_field": "x"}, allowed)
    assert any("sneaky_field" in v for v in violations)


def test_scan_record_clean_record_has_no_violations() -> None:
    allowed = load_allowed_keys()
    violations = scan_record(
        {"seq": 0, "kind": "marker_read", "peer_pid": 1, "peer_exe": "python", "path": "/v1/token"},
        allowed,
    )
    assert violations == []


def test_scan_record_recurses_into_nested_receipt_body() -> None:
    allowed = load_allowed_keys()
    record = {
        "seq": 0,
        "kind": "receipt",
        "body": {"run_id": "r1", "raw_leak_field": "nope"},
        "sig": "abc",
    }
    violations = scan_record(record, allowed)
    assert any("raw_leak_field" in v for v in violations)


def test_findings_dynamic_keys_are_whitelisted() -> None:
    allowed = load_allowed_keys()
    record = {
        "seq": 0,
        "kind": "receipt",
        "body": {"findings": {"marker_read": 2, "outbound_post": 1}},
        "sig": "abc",
    }
    violations = scan_record(record, allowed)
    assert violations == []


def test_contains_secret_detects_aws_key() -> None:
    assert contains_secret(_AWS_KEY_SHAPED_FIXTURE) is not None


def test_contains_secret_allows_wellformed_decoy_value() -> None:
    assert contains_secret("WITNESS-DECOY-0a1b2c3d") is None


def test_looks_like_prose_flags_long_wordy_string() -> None:
    sentence = "this is a long sentence with many words " * 6
    assert looks_like_prose(sentence) is True


def test_looks_like_prose_allows_long_digest() -> None:
    long_hex = "ab" * 150
    assert looks_like_prose(long_hex) is False


def test_cli_exits_3_on_disallowed_key(tmp_path: Path) -> None:
    bad = tmp_path / "bundle.jsonl"
    bad.write_text(json.dumps({"seq": 0, "kind": "manifest", "raw_prompt_text": "leak"}) + "\n")

    result = subprocess.run(
        [sys.executable, str(_LEAKSCAN_SCRIPT), str(bad)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3
    assert "raw_prompt_text" in result.stderr


def test_cli_exits_0_on_clean_bundle(tmp_path: Path) -> None:
    clean = tmp_path / "bundle.jsonl"
    clean.write_text(json.dumps({"seq": 0, "kind": "manifest", "run_id": "r1"}) + "\n")

    result = subprocess.run(
        [sys.executable, str(_LEAKSCAN_SCRIPT), str(clean)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_changed_file_digests_arbitrary_paths_are_not_disallowed_keys() -> None:
    """`changed_file_digests`'s own keys are relative file paths — content,
    not a fixed schema vocabulary — so the generic key-whitelist check
    must not flag them, unlike every other nested dict in a record."""
    allowed = load_allowed_keys()
    record = {
        "seq": 0,
        "kind": "receipt",
        "body": {
            "changed_file_digests": {
                "src/foo/bar.py": "a" * 64,
                "README.md": "b" * 64,
            }
        },
        "sig": "abc",
    }
    violations = scan_record(record, allowed)
    assert violations == []


def test_changed_file_digests_keys_are_still_scanned_for_secrets() -> None:
    """A path-keyed field's keys are exempt from the whitelist check, but
    NOT from secret-pattern scanning — a key can't be used to smuggle a
    secret-shaped string past the scan just because it's "a path"."""
    allowed = load_allowed_keys()
    record = {
        "seq": 0,
        "kind": "receipt",
        "body": {"changed_file_digests": {_AWS_KEY_SHAPED_FIXTURE: "a" * 64}},
        "sig": "abc",
    }
    violations = scan_record(record, allowed)
    assert any("secret-shaped" in v for v in violations)


def test_changed_file_digests_values_still_scanned_for_secrets() -> None:
    allowed = load_allowed_keys()
    record = {
        "seq": 0,
        "kind": "receipt",
        "body": {"changed_file_digests": {"src/foo.py": _AWS_KEY_SHAPED_FIXTURE}},
        "sig": "abc",
    }
    violations = scan_record(record, allowed)
    assert any("secret-shaped" in v for v in violations)


def test_other_dicts_are_unaffected_by_path_keyed_exemption() -> None:
    """A plain, non-exempt dict field (e.g. a hypothetical nested object
    under a different key) still gets its keys checked normally — the
    exemption in `scan_value` is scoped to `_PATH_KEYED_FIELDS` only."""
    violations = scan_value(
        "$.body",
        {"findings": {"not_a_real_finding_kind_or_field": 1}},
        load_allowed_keys(),
        _parent_key="body",
    )
    assert any("not_a_real_finding_kind_or_field" in v for v in violations)
