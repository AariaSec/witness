"""Ledger: hash-chain integrity, seq contiguity, tamper detection, close."""

from __future__ import annotations

import json
from pathlib import Path

from witness.ledger import Ledger, read_ledger, verify_chain
from witness.models import Manifest, MarkerRead


def _manifest(run_id: str = "test-run") -> Manifest:
    return Manifest(
        bundle_schema="1.0",
        witness_version="0.1.0",
        run_id=run_id,
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


def test_append_assigns_seq_and_chain(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    r0 = ledger.append(_manifest())
    r1 = ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    assert r0.seq == 0
    assert r1.seq == 1
    assert r0.prev is None
    assert r1.prev == r0.digest
    ledger.close()


def test_verify_chain_true_on_clean_ledger(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.append(MarkerRead(peer_pid=2, peer_exe="y"))
    ledger.close()

    records = read_ledger(path)
    assert len(records) == 3
    assert [r.seq for r in records] == [0, 1, 2]
    ok, bad = verify_chain(records)
    assert ok is True
    assert bad is None


def test_verify_chain_detects_tamper(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.close()

    lines = path.read_text().splitlines()
    obj = json.loads(lines[1])
    obj["peer_exe"] = "TAMPERED"
    lines[1] = json.dumps(obj)
    path.write_text("\n".join(lines) + "\n")

    records = read_ledger(path)
    ok, bad = verify_chain(records)
    assert ok is False
    assert bad == 1


def test_verify_chain_detects_reordering(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.append(MarkerRead(peer_pid=2, peer_exe="y"))
    ledger.close()

    lines = path.read_text().splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    path.write_text("\n".join(lines) + "\n")

    records = read_ledger(path)
    ok, bad = verify_chain(records)
    assert ok is False
    assert bad is not None


def test_close_returns_final_digest(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    r0 = ledger.append(_manifest())
    final = ledger.close()
    assert final == r0.digest


def test_record_count(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    assert ledger.record_count == 0
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    assert ledger.record_count == 2
    ledger.close()


def test_on_append_callback_invoked(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    seen = []
    ledger.on_append(lambda rec: seen.append(rec.kind))
    ledger.append(_manifest())
    ledger.append(MarkerRead(peer_pid=1, peer_exe="x"))
    ledger.close()
    assert seen == ["manifest", "marker_read"]
