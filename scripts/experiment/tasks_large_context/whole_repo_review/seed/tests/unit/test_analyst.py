"""Analyst: offline deterministic template (default) + the opt-in live path.

The live-path tests here use a fake, deterministic `LLMClient` — no
network, no API key, keeps CI free and fast. The live path's actual
behavior against the real Baseten/Muse Spark Open API was verified
manually (see docs/NUMBERS.md) rather than in the automated suite, since
a real network call has no place in a gate that must stay green offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from witness.analyst.client import LLMClientError
from witness.analyst.run import analyze
from witness.analyst.tools import get_record, query
from witness.bundle import build_bundle
from witness.ledger import Ledger
from witness.models import Finding, FindingKind, Manifest, MarkerRead, Severity


class _FakeClient:
    """Deterministic stand-in for `LLMClient` — returns canned responses
    from a queue, one per `complete()` call, so tests can script retries."""

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def complete(
        self,
        system: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        schema: dict[str, object],
    ) -> dict[str, object]:
        self.calls += 1
        return self._responses.pop(0)


class _RaisingClient:
    def complete(
        self,
        system: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        schema: dict[str, object],
    ) -> dict[str, object]:
        raise LLMClientError("simulated network failure")


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


def test_analyze_offline_no_findings(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ledger = Ledger(run_dir / "ledger.jsonl")
    ledger.append(_manifest())
    ledger.close()
    bundle_path = run_dir / "bundle.jsonl"
    build_bundle(run_dir, bundle_path)

    report = analyze(bundle_path, client=None)
    assert report.analyst_status == "offline"
    assert report.tool_calls == 0
    assert report.summary_codes == ["NO_FINDINGS"]
    assert report.confidence == 1.0
    assert all(len(code) <= 64 for code in report.summary_codes)


def test_analyze_offline_with_findings(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ledger = Ledger(run_dir / "ledger.jsonl")
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.append(
        Finding(
            fkind=FindingKind.marker_read,
            severity=Severity.warn,
            evidence_seqs=[1],
            detector_version="1.0",
        )
    )
    ledger.close()
    bundle_path = run_dir / "bundle.jsonl"
    build_bundle(run_dir, bundle_path)

    report = analyze(bundle_path, client=None)
    assert report.analyst_status == "offline"
    assert "DECOY_KEY_READ" in report.summary_codes
    assert len(report.timeline) == 1
    assert report.timeline[0].seq_refs == [1]


def test_analyst_tools_get_record_and_query() -> None:
    records = [
        {"seq": 0, "kind": "manifest", "run_id": "r1"},
        {"seq": 1, "kind": "marker_read", "peer_pid": 1},
        {"seq": 2, "kind": "marker_read", "peer_pid": 2},
    ]
    assert get_record(records, 1)["peer_pid"] == 1
    matched = query(records, "marker_read")
    assert len(matched) == 2
    filtered = query(records, "marker_read", {"peer_pid": 2})
    assert len(filtered) == 1
    assert filtered[0]["seq"] == 2


def test_analyst_tools_get_record_missing_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_record([{"seq": 0, "kind": "manifest"}], 99)


def _findings_bundle(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ledger = Ledger(run_dir / "ledger.jsonl")
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.append(
        Finding(
            fkind=FindingKind.marker_read,
            severity=Severity.warn,
            evidence_seqs=[1],
            detector_version="1.0",
        )
    )
    ledger.close()
    bundle_path = run_dir / "bundle.jsonl"
    build_bundle(run_dir, bundle_path)
    return bundle_path


_VALID_LIVE_RESPONSE = {
    "summary_codes": ["DECOY_KEY_READ"],
    "timeline": [{"seq_refs": [1], "code": "DECOY_KEY_READ", "severity": "warn"}],
    "reported_vs_recorded": [],
    "confidence": 0.9,
}


def test_analyze_live_success(tmp_path: Path) -> None:
    bundle_path = _findings_bundle(tmp_path)
    client = _FakeClient([_VALID_LIVE_RESPONSE])

    report = analyze(bundle_path, client=client, model_id="fake-model-1")

    assert report.analyst_status == "ok"
    assert report.model_id == "fake-model-1"
    assert report.tool_calls == 1
    assert client.calls == 1
    assert report.summary_codes == ["DECOY_KEY_READ"]
    assert report.confidence == 0.9


def test_analyze_live_retries_once_on_schema_failure_then_succeeds(tmp_path: Path) -> None:
    bundle_path = _findings_bundle(tmp_path)
    # First response is missing required fields (schema failure); second is valid.
    client = _FakeClient([{"summary_codes": ["X"]}, _VALID_LIVE_RESPONSE])

    report = analyze(bundle_path, client=client, model_id="fake-model-1")

    assert report.analyst_status == "ok"
    assert report.tool_calls == 2  # the retry counts as a second tool call
    assert client.calls == 2


def test_analyze_live_falls_back_to_offline_after_two_schema_failures(tmp_path: Path) -> None:
    bundle_path = _findings_bundle(tmp_path)
    bad = {"summary_codes": ["X"]}  # missing required fields both times
    client = _FakeClient([bad, bad])

    report = analyze(bundle_path, client=client, model_id="fake-model-1")

    assert report.analyst_status == "offline"
    assert report.model_id == "offline-template"
    assert client.calls == 2


def test_analyze_live_falls_back_to_offline_on_client_error(tmp_path: Path) -> None:
    bundle_path = _findings_bundle(tmp_path)

    report = analyze(bundle_path, client=_RaisingClient(), model_id="fake-model-1")

    assert report.analyst_status == "offline"
    assert "DECOY_KEY_READ" in report.summary_codes


def test_analyze_live_never_raises_on_malformed_json_content(tmp_path: Path) -> None:
    """A client whose `complete()` itself returns something analyze() can't
    use (e.g. a non-dict) must still fall back cleanly, not crash the run."""
    bundle_path = _findings_bundle(tmp_path)

    class _BadShapeClient:
        def complete(
            self,
            system: str,
            messages: list[dict[str, object]],
            tools: list[dict[str, object]],
            schema: dict[str, object],
        ) -> dict[str, object]:
            return {"totally": "wrong-shape"}

    report = analyze(bundle_path, client=_BadShapeClient(), model_id="fake-model-1")
    assert report.analyst_status == "offline"


def test_fake_client_json_roundtrip_sanity() -> None:
    """Sanity check the fixture values are themselves valid JSON (catches a
    typo in a test fixture before it masquerades as a product bug)."""
    json.dumps(_VALID_LIVE_RESPONSE)
