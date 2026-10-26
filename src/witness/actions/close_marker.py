"""Action: close the decoy marker service (serves 410 afterwards)."""

from __future__ import annotations

import time

from witness.listeners.marker import MarkerService
from witness.models import ActionResult


def close_marker(marker: MarkerService, finding_seq: int) -> ActionResult:
    start = time.monotonic()
    already = marker._closed.is_set()
    try:
        marker.close_token()
        ok = True
        detail = "already_closed" if already else "noop"
    except Exception:
        ok = False
        detail = "failed"
    latency_ms = int((time.monotonic() - start) * 1000)
    return ActionResult(
        action="close_marker",
        finding_seq=finding_seq,
        ok=ok,
        latency_ms=latency_ms,
        detail=detail,  # type: ignore[arg-type]
    )


__all__ = ["close_marker"]
