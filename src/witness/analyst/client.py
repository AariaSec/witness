"""`LLMClient` protocol — the shape a real Muse Spark / partner API adapter
implements — plus `BasetenClient`, a real (opt-in) adapter for Meta's
open-weight Muse Spark Open model via Baseten's OpenAI-compatible endpoint.

The offline deterministic template in `analyst/run.py` remains the default,
always-available path (see that module's docstring for why: the judge-
facing product must never depend on a live call that could fail). This
client exists so the project can ALSO point at a real Meta open-weight
model when one is available, satisfying "meaningfully use Meta Model API
and/or Meta open-weight models" without making it a requirement to run.

No prompt/response text ever reaches this client beyond the bundle's own
digests/enums/counts (RULE 1 analog) — the caller is responsible for never
passing anything else.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

DEFAULT_BASETEN_URL = "https://inference.baseten.co/v1/chat/completions"
DEFAULT_BASETEN_MODEL = "meta-models/muse-spark-open-1026"
DEFAULT_BASETEN_KEY_PATH = Path.home() / ".config" / "aariasec" / "baseten_api_key"


class LLMClient(Protocol):
    def complete(
        self,
        system: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        schema: dict[str, object],
    ) -> dict[str, object]: ...


class LLMClientError(RuntimeError):
    """Raised on any live-call failure (network, timeout, bad response).

    `analyst/run.py` catches this and falls back to the offline template —
    this is the designed failure path, not an unhandled error.
    """


class BasetenClient:
    """Real adapter for Muse Spark Open via Baseten's OpenAI-compatible API.

    A reasoning model: it writes a chain of thought into
    `message.reasoning_content` before the final answer lands in
    `message.content` — `max_tokens` must leave room for both, or the
    response truncates with `content` empty. Hard-capped on timeout and
    `max_tokens` so a single analyst pass has a bounded, predictable cost;
    `tools` is accepted for protocol compatibility but unused (see
    `analyst/run.py` for why a single-shot call is used instead of a
    multi-turn tool loop).
    """

    def __init__(
        self,
        api_key: str | None = None,
        key_path: Path = DEFAULT_BASETEN_KEY_PATH,
        base_url: str = DEFAULT_BASETEN_URL,
        model: str = DEFAULT_BASETEN_MODEL,
        max_tokens: int = 6000,
        timeout_s: float = 60.0,
    ) -> None:
        self._api_key = api_key or self._read_key(key_path)
        self._base_url = base_url
        self._model = model
        self._max_tokens = max_tokens
        self._timeout_s = timeout_s

    @staticmethod
    def _read_key(key_path: Path) -> str:
        try:
            return key_path.read_text().strip()
        except OSError as exc:
            raise LLMClientError(f"no Baseten key at {key_path}") from exc

    def complete(
        self,
        system: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        schema: dict[str, object],
    ) -> dict[str, object]:
        del tools  # unused — see class docstring
        full_messages = [{"role": "system", "content": system}, *messages]
        body = json.dumps(
            {
                "model": self._model,
                "messages": full_messages,
                "max_tokens": self._max_tokens,
                "response_format": {"type": "json_object"},
            }
        ).encode()

        req = urllib.request.Request(
            self._base_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMClientError(f"Baseten call failed: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"unexpected Baseten response shape: {data}") from exc

        if not content:
            raise LLMClientError(
                "Baseten response had empty content (likely truncated by max_tokens)"
            )

        try:
            return json.loads(content)  # type: ignore[no-any-return]
        except json.JSONDecodeError as exc:
            raise LLMClientError(f"analyst output was not valid JSON: {content[:200]}") from exc


__all__ = ["BasetenClient", "LLMClient", "LLMClientError"]
