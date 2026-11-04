"""A small-context client (Glimmer) gets one call per window of records, merged conservatively; a normal client gets one call."""

from __future__ import annotations

from pathlib import Path

from witness.analyst.run import _live_report_auto
from witness.ledger import read_ledger

_REPO = Path(__file__).resolve().parents[2]
_BUNDLE = _REPO / "runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl"  # 22 records
_PROMPT = _REPO / "src/witness/analyst/prompt_v1.md"


class _Fake:
    """Returns one step per call citing the first seq it was shown; confidence falls with each call."""

    def __init__(self, chunk: int | None) -> None:
        self.chunk_records = chunk
        self.calls = 0
        self.sizes: list[int] = []

    def complete(self, system, messages, tools, schema):  # type: ignore[no-untyped-def]
        import json

        recs = json.loads(messages[0]["content"].split("Records:\n", 1)[1])
        self.calls += 1
        self.sizes.append(len(recs))
        return {"summary_codes": ["PROC_SPAWN", f"RECEIPT_SIGNED" if self.calls % 2 else "PROC_SPAWN"],
                "timeline": [{"seq_refs": [recs[0]["seq"]], "code": "PROC_SPAWN", "severity": "info"}],
                "reported_vs_recorded": [], "confidence": round(0.9 - 0.1 * self.calls, 2)}


def test_normal_client_makes_one_call() -> None:
    c = _Fake(None)
    rep = _live_report_auto(read_ledger(_BUNDLE), c, _PROMPT, "m")
    assert c.calls == 1 and len(rep.timeline) == 1


def test_small_context_client_is_windowed_and_merged() -> None:
    c = _Fake(10)
    rep = _live_report_auto(read_ledger(_BUNDLE), c, _PROMPT, "m")
    assert c.sizes == [10, 10, 2]  # 22 records in windows of 10
    assert len(rep.timeline) == 3  # one step per window, concatenated
    assert rep.summary_codes == ["PROC_SPAWN", "RECEIPT_SIGNED"]  # unioned, order kept, no duplicates
    assert rep.confidence == 0.6  # the minimum over windows (0.8, 0.7, 0.6)
    assert rep.tool_calls == 3 and rep.analyst_status == "ok"
