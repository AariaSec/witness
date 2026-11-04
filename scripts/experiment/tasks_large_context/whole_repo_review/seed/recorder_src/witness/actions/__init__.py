"""Policy table + action runner.

`POLICY` maps a `FindingKind` to the ordered list of actions to run. The
`ActionRunner` executes them and appends each outcome to the ledger as an
`ActionResult` — including failures (fail-visible, not fail-silent).
"""

from __future__ import annotations

import time

from witness.actions.close_marker import close_marker
from witness.actions.receipt import Signer
from witness.actions.stop_pgroup import stop_pgroup as _stop_pgroup
from witness.ledger import Ledger
from witness.listeners.marker import MarkerService
from witness.models import ActionResult, Finding, FindingKind, Receipt, ReceiptBody, Severity

POLICY: dict[FindingKind, list[str]] = {
    FindingKind.marker_read: ["close_marker"],
    FindingKind.outbound_post: ["close_marker", "stop_pgroup"],
    FindingKind.protected_write: ["stop_pgroup"],
    FindingKind.pgroup_escape: ["stop_pgroup"],
    FindingKind.mismatch: [],
    FindingKind.drift: [],
}


class ActionRunner:
    """Runs the policy for a `Finding` and appends `ActionResult`s."""

    def __init__(
        self,
        marker: MarkerService,
        pgid: int,
        ledger: Ledger,
        signer: Signer,
        extra_pids: set[int] | None = None,
    ) -> None:
        self._marker = marker
        self._pgid = pgid
        self._ledger = ledger
        self._signer = signer
        self._extra_pids = extra_pids if extra_pids is not None else set()

    def note_extra_pid(self, pid: int) -> None:
        """Record a pid seen talking to the marker/sink that may not be in
        the recorded process group (pgroup-escape fallback target)."""
        self._extra_pids.add(pid)

    @property
    def extra_pids(self) -> set[int]:
        return self._extra_pids

    def sign_receipt(self, body: ReceiptBody) -> Receipt:
        """Sign a `ReceiptBody` with this runner's `Signer`. `sign_receipt`
        is not driven by `POLICY` (no finding maps to it) — it's always the
        last action of a run, called once at `run_end`."""
        return self._signer.sign(body)

    def handle(self, finding: Finding) -> list[ActionResult]:
        action_names = POLICY.get(finding.fkind, [])
        results: list[ActionResult] = []
        for action in action_names:
            if action == "close_marker":
                result = close_marker(self._marker, finding.seq)
            elif action == "stop_pgroup":
                # Destructive — gated on severity, not just kind. POLICY's
                # table presupposes a fixed severity per fkind, which held
                # for every entry except pgroup_escape once that detector
                # started emitting BOTH warn (bare detachment, no
                # corroborating decoy contact) and stop (detachment +
                # decoy contact) for the same fkind — a warn-severity
                # finding killing the whole process group would be the
                # exact "gate that red-X's honest sessions" failure mode
                # this project is built to avoid, not cause.
                if finding.severity != Severity.stop:
                    continue
                result = self._do_stop(finding.seq)
            else:
                continue
            appended = self._ledger.append(result)
            results.append(appended)  # type: ignore[arg-type]
        return results

    def _do_stop(self, finding_seq: int) -> ActionResult:
        start = time.monotonic()
        status = _stop_pgroup(self._pgid, self._extra_pids)
        latency_ms = int((time.monotonic() - start) * 1000)
        ok = status in ("term", "kill")
        return ActionResult(
            action="stop_pgroup",
            finding_seq=finding_seq,
            ok=ok,
            latency_ms=latency_ms,
            detail=status,
        )


__all__ = ["POLICY", "ActionRunner"]
