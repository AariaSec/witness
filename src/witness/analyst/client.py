"""`LLMClient` protocol — the shape a real Muse Spark / partner API adapter
would implement. Not wired to a live call in G1 (see `analyst/run.py`):
the offline deterministic template is the only path exercised, since the
G1 exit criteria require the analyst step to work with zero API key."""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def complete(
        self,
        system: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        schema: dict[str, object],
    ) -> dict[str, object]: ...


__all__ = ["LLMClient"]
