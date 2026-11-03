"""GlimmerClient: endpoint comes from WITNESS_GLIMMER_URL, no key, URL normalized."""

import pytest

from witness.analyst.client import GlimmerClient, LLMClientError


def test_requires_endpoint(monkeypatch):
    monkeypatch.delenv("WITNESS_GLIMMER_URL", raising=False)
    with pytest.raises(LLMClientError):
        GlimmerClient()


@pytest.mark.parametrize(
    "given",
    [
        "https://x.modal.run",
        "https://x.modal.run/",
        "https://x.modal.run/v1",
        "https://x.modal.run/v1/chat/completions",
    ],
)
def test_url_is_normalized_to_chat_completions(monkeypatch, given):
    monkeypatch.setenv("WITNESS_GLIMMER_URL", given)
    assert GlimmerClient()._base_url == "https://x.modal.run/v1/chat/completions"


def test_explicit_base_url_wins(monkeypatch):
    monkeypatch.setenv("WITNESS_GLIMMER_URL", "https://env.modal.run")
    assert GlimmerClient(base_url="https://arg.modal.run")._base_url == "https://arg.modal.run/v1/chat/completions"
