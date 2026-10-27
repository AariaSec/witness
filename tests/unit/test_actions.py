"""Actions: stop_pgroup kills a process tree; Signer sign/verify roundtrip."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from witness.actions.receipt import Signer, verify_receipt
from witness.actions.stop_pgroup import stop_pgroup
from witness.models import ReceiptBody


def test_stop_pgroup_kills_sleeping_child_tree() -> None:
    proc = subprocess.Popen(["sleep", "30"], preexec_fn=os.setsid)
    pgid = os.getpgid(proc.pid)
    time.sleep(0.2)

    status = stop_pgroup(pgid, grace_s=2.0)

    assert status in ("term", "kill")
    # Child must be dead within 2.5s of the call above (already elapsed).
    deadline = time.monotonic() + 0.5
    dead = False
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            dead = True
            break
        time.sleep(0.05)
    assert dead, "child process tree should be dead shortly after stop_pgroup"


def test_stop_pgroup_defaults_were_investigated_not_blindly_widened() -> None:
    """2026-10-27: a real Modal-cloud run reported stop_pgroup "failed" at
    3009ms (the then-default 2.0s grace + 1.0s kill-wait). Widened to
    3.0s/2.0s (5.0s total) -- still "failed", at 5023ms. Widened again to
    5.0s/3.0s (8.0s total) -- still "failed", at 8024ms. The overshoot
    stayed ~20-24ms (one poll tick) at every budget tried, proving the
    process group was never actually detected dead within ANY window --
    not a timing-margin problem, so widening further would only waste
    wall-clock time. Reverted to the original 2.0s/1.0s; see
    docs/LIMITATIONS.md for the real, still-open finding (signal delivery
    to a process group likely doesn't work the same way under Modal's
    sandboxed container runtime). This test exists so a future "just
    widen it more" fix doesn't get tried again without reading that
    writeup first."""
    import inspect

    sig = inspect.signature(stop_pgroup)
    assert sig.parameters["grace_s"].default == 2.0
    assert sig.parameters["kill_wait_s"].default == 1.0


def test_stop_pgroup_on_already_dead_group_is_noop_success() -> None:
    proc = subprocess.Popen(["true"], preexec_fn=os.setsid)
    pgid = os.getpgid(proc.pid)
    proc.wait()
    time.sleep(0.1)
    status = stop_pgroup(pgid, grace_s=0.5)
    assert status == "term"


def test_signer_roundtrip(tmp_path: Path) -> None:
    signer = Signer.load_or_create(tmp_path)
    body = ReceiptBody(
        run_id="r1",
        final_digest="0" * 64,
        records=5,
        findings={"marker_read": 1},
        stop_status="ok",
        policy_hash="0" * 64,
        signed_at=1.0,
        pubkey=signer.public_key_b64,
    )
    receipt = signer.sign(body)
    assert verify_receipt(receipt) is True


def test_signer_verify_false_on_tampered_body(tmp_path: Path) -> None:
    signer = Signer.load_or_create(tmp_path)
    body = ReceiptBody(
        run_id="r1",
        final_digest="0" * 64,
        records=5,
        findings={},
        stop_status="not_needed",
        policy_hash="0" * 64,
        signed_at=1.0,
        pubkey=signer.public_key_b64,
    )
    receipt = signer.sign(body)
    tampered = receipt.model_copy(update={"body": body.model_copy(update={"records": 999})})
    assert verify_receipt(tampered) is False


def test_signer_key_file_permissions(tmp_path: Path) -> None:
    Signer.load_or_create(tmp_path)
    priv = tmp_path / "ed25519_private.pem"
    assert priv.exists()
    mode = oct(priv.stat().st_mode)[-3:]
    assert mode == "600"


def test_signer_load_existing_key_is_stable(tmp_path: Path) -> None:
    s1 = Signer.load_or_create(tmp_path)
    s2 = Signer.load_or_create(tmp_path)
    assert s1.public_key_b64 == s2.public_key_b64
