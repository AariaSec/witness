"""Tests for `witness.claude_journal` — the real Claude Code session
`.jsonl` parser.

`tests/fixtures/claude_journal/success_session.txt` and
`denied_session.txt` are SANITIZED copies of two real captures (`claude`
v2.1.310, 2026-10-26/27, in a disposable throwaway scratch directory):
same task (write `hello.txt`) run twice, once with the Write tool granted
and once denied. Every `content`/`rendered`/`shape`/`params`/
`originalFile`/`structuredPatch`/`message`/`input`/`text`/`prompt`-keyed
string value, and any string over 200 chars, was replaced with a
placeholder before these files were committed. No raw prompt or response
text from any real session is or was ever committed to this repo.
"""

from __future__ import annotations

from pathlib import Path

from witness.claude_journal import (
    ClaudeCodeClaimParser,
    claim_from_record,
    iter_session_file,
)
from witness.models import AssistantClaim, TailMeta

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "claude_journal"
SUCCESS_FIXTURE = _FIXTURE_DIR / "success_session.txt"
DENIED_FIXTURE = _FIXTURE_DIR / "denied_session.txt"


def _success_tool_result_record(
    *, file_path: str = "/private/tmp/claude_format_spike/hello.txt", patch_len: int = 0
) -> dict:
    """The actual confirmed shape of a `user` record following a
    successful `Write`, trimmed to the fields this module reads plus a
    couple of neighbors, matching `success_session.txt` line 22."""
    return {
        "parentUuid": "3881b795-73c9-4400-b9a2-3e79f9e13879",
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "tool_use_id": "toolu_01VPaakwWgYqebjvk2BJpxJi",
                    "type": "tool_result",
                    "content": "PLACEHOLDER_CONTENT",
                }
            ],
        },
        "uuid": "32cfdce5-3327-48bb-bc93-0520a73ac38f",
        "toolUseResult": {
            "type": "create",
            "filePath": file_path,
            "content": "PLACEHOLDER_CONTENT",
            "structuredPatch": [{"placeholder": True}] * patch_len,
            "originalFile": None,
            "userModified": False,
        },
        "permissionDecision": {
            "decision": "accept",
            "source": "config",
            "reasonType": "rule",
            "ruleSource": "cliArg",
        },
        "sessionId": "ef9be31f-c2e5-4411-bcbe-86bed704739c",
    }


def _denied_tool_result_record() -> dict:
    """The actual confirmed shape of a `user` record following a denied
    `Write`, matching `denied_session.txt` line 21."""
    return {
        "parentUuid": "9c807fb2-34d1-4e72-87ef-7a2c7afd6d0f",
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "content": "PLACEHOLDER_CONTENT",
                    "is_error": True,
                    "tool_use_id": "toolu_015aNY2QNDWNhktfiQ1r8cES",
                }
            ],
        },
        "uuid": "affbdf97-7c0e-4edd-a37f-1041989c704f",
        "toolUseResult": (
            "Error: Claude requested permissions to write to "
            "/private/tmp/claude_format_spike/hello.txt, but you haven't granted it yet."
        ),
        "toolDenialKind": "user-rejected",
        "permissionDecision": {"decision": "reject", "source": "config", "reasonCode": "unknown"},
        "sessionId": "00545c25-f2f7-41fc-a6fe-1077b25d904f",
    }


def _assistant_tool_use_record() -> dict:
    """An `assistant` record carrying a `Write` tool_use block — never
    itself turned into a claim (see module docstring), included here only
    to prove `claim_from_record` ignores non-`user` records cleanly."""
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_01VPaakwWgYqebjvk2BJpxJi",
                    "name": "Write",
                    "input": {
                        "file_path": "/private/tmp/claude_format_spike/hello.txt",
                        "content": "PLACEHOLDER_CONTENT",
                    },
                }
            ],
        },
        "wireToolInputs": {
            "toolu_01VPaakwWgYqebjvk2BJpxJi": {
                "file_path": "/private/tmp/claude_format_spike/hello.txt",
                "content": "PLACEHOLDER_CONTENT",
            }
        },
    }


# --- claim_from_record: the success shape --------------------------------


def test_claim_from_record_recognizes_real_write_success() -> None:
    rec = _success_tool_result_record()
    claim = claim_from_record(rec)
    assert claim is not None
    assert claim.tool == "write"
    assert claim.claimed_paths == ["/private/tmp/claude_format_spike/hello.txt"]
    assert claim.claimed_count == 0
    assert claim.claimed_hosts == []
    # Content-bearing fields must never leak into the claim.
    dumped = claim.model_dump_json()
    assert "PLACEHOLDER_CONTENT" not in dumped


def test_claim_from_record_counts_structured_patch_entries() -> None:
    rec = _success_tool_result_record(patch_len=3)
    claim = claim_from_record(rec)
    assert claim is not None
    assert claim.claimed_count == 3


# --- claim_from_record: the denial shape (deliberately None) --------------


def test_claim_from_record_denial_returns_none() -> None:
    rec = _denied_tool_result_record()
    assert claim_from_record(rec) is None


def test_claim_from_record_is_error_without_denial_kind_also_returns_none() -> None:
    # Belt-and-suspenders: either signal alone is enough to withhold a claim.
    rec = _success_tool_result_record()
    rec["message"]["content"][0]["is_error"] = True
    assert claim_from_record(rec) is None


# --- claim_from_record: ignores everything else ---------------------------


def test_claim_from_record_ignores_assistant_record() -> None:
    # The tool_use request side never itself produces a claim — see
    # module docstring "why the claim comes from the result side".
    assert claim_from_record(_assistant_tool_use_record()) is None


def test_claim_from_record_ignores_non_tool_result_user_record() -> None:
    rec = {"type": "user", "message": {"role": "user", "content": "PLACEHOLDER_CONTENT"}}
    assert claim_from_record(rec) is None


def test_claim_from_record_unobserved_tool_result_type_returns_none() -> None:
    # Only "create" has ever been observed — "update" (an overwrite) is a
    # plausible but unconfirmed shape and must not be guessed at.
    rec = _success_tool_result_record()
    rec["toolUseResult"]["type"] = "update"
    assert claim_from_record(rec) is None


def test_claim_from_record_missing_file_path_returns_none() -> None:
    rec = _success_tool_result_record()
    del rec["toolUseResult"]["filePath"]
    assert claim_from_record(rec) is None


def test_claim_from_record_never_raises_on_garbage() -> None:
    assert claim_from_record({}) is None
    assert claim_from_record({"type": "user"}) is None
    assert claim_from_record({"type": "user", "message": "not-a-dict"}) is None
    assert claim_from_record({"type": "user", "message": {"content": "not-a-list"}}) is None
    assert claim_from_record({"type": "user", "message": {"content": [1, 2, "x"]}}) is None
    assert claim_from_record(None) is None  # type: ignore[arg-type]
    assert claim_from_record("not even a dict") is None  # type: ignore[arg-type]


# --- ClaudeCodeClaimParser (ClaimParser protocol) -------------------------


def test_parser_success_line_emits_one_claim() -> None:
    parser = ClaudeCodeClaimParser()
    import json

    line = json.dumps(_success_tool_result_record()).encode()
    out = parser.parse_line(line, "session_log")
    assert len(out) == 1
    assert isinstance(out[0], AssistantClaim)
    assert out[0].tool == "write"


def test_parser_denied_line_emits_nothing() -> None:
    parser = ClaudeCodeClaimParser()
    import json

    line = json.dumps(_denied_tool_result_record()).encode()
    assert parser.parse_line(line, "session_log") == []


def test_parser_empty_line_returns_empty_list() -> None:
    parser = ClaudeCodeClaimParser()
    assert parser.parse_line(b"", "session_log") == []
    assert parser.parse_line(b"   \n", "session_log") == []


def test_parser_invalid_json_returns_parse_error_meta() -> None:
    parser = ClaudeCodeClaimParser()
    out = parser.parse_line(b"{not json", "session_log")
    assert len(out) == 1
    assert isinstance(out[0], TailMeta)
    assert out[0].event == "parse_error"


def test_parser_non_dict_json_returns_parse_error_meta() -> None:
    parser = ClaudeCodeClaimParser()
    out = parser.parse_line(b"[1,2,3]", "session_log")
    assert len(out) == 1
    assert isinstance(out[0], TailMeta)
    assert out[0].event == "parse_error"


def test_parser_oversized_line_returns_parse_error_meta() -> None:
    parser = ClaudeCodeClaimParser()
    huge = b'{"type": "user", "x": "' + b"9" * (3 * 1024 * 1024) + b'"}'
    out = parser.parse_line(huge, "session_log")
    assert len(out) == 1
    assert isinstance(out[0], TailMeta)
    assert out[0].event == "parse_error"
    assert out[0].bytes_skipped == len(huge)


def test_parser_unrecognized_but_valid_record_is_quietly_dropped() -> None:
    import json

    parser = ClaudeCodeClaimParser()
    out = parser.parse_line(json.dumps({"type": "cost-state"}).encode(), "session_log")
    assert out == []


# --- against the real sanitized fixtures ----------------------------------


def test_success_fixture_contains_no_unredacted_prose() -> None:
    raw = SUCCESS_FIXTURE.read_text()
    assert "PLACEHOLDER_CONTENT" in raw  # the sanitization marker IS expected
    # Regression guard: an earlier pass of sanitization matched the exact
    # key "prompt" and missed the camelCase `lastPrompt` field, which
    # carried this real session's literal task text unredacted. Fixed in
    # this same commit — this assertion fails loudly if it regresses.
    assert "lastPrompt" not in raw or '"lastPrompt": "PLACEHOLDER_CONTENT"' in raw
    assert "create a file named hello.txt" not in raw.lower()
    assert "containing exactly the word hello" not in raw.lower()


def test_denied_fixture_contains_no_unredacted_prose() -> None:
    raw = DENIED_FIXTURE.read_text()
    assert "lastPrompt" not in raw or '"lastPrompt": "PLACEHOLDER_CONTENT"' in raw
    assert "create a file named hello.txt" not in raw.lower()
    assert "containing exactly the word hello" not in raw.lower()


def test_iter_session_file_against_success_fixture() -> None:
    records = list(iter_session_file(SUCCESS_FIXTURE))
    assert len(records) == 30
    types = {r.get("type") for r in records}
    assert "assistant" in types
    assert "user" in types


def test_iter_session_file_against_success_fixture_finds_one_write_claim() -> None:
    records = list(iter_session_file(SUCCESS_FIXTURE))
    claims = [c for c in (claim_from_record(r) for r in records) if c is not None]
    assert len(claims) == 1
    assert claims[0].tool == "write"
    assert claims[0].claimed_paths == ["/private/tmp/claude_format_spike/hello.txt"]


def test_iter_session_file_against_denied_fixture_finds_no_claims() -> None:
    records = list(iter_session_file(DENIED_FIXTURE))
    assert len(records) == 33
    claims = [c for c in (claim_from_record(r) for r in records) if c is not None]
    assert claims == []


def test_parser_tails_the_success_fixture_as_a_live_file(tmp_path: Path) -> None:
    from witness.tailer import Tailer

    target = tmp_path / "session.jsonl"
    target.write_text("")
    events: list[AssistantClaim | TailMeta] = []
    tailer = Tailer([target], parser=ClaudeCodeClaimParser())
    tailer.start(lambda rec: events.append(rec))
    try:
        with open(target, "a") as fh:
            fh.write(SUCCESS_FIXTURE.read_text())
        import time

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            time.sleep(0.05)
        claims = [e for e in events if isinstance(e, AssistantClaim)]
        assert len(claims) == 1
        assert claims[0].tool == "write"
        assert not any(isinstance(e, TailMeta) and e.event == "parse_error" for e in events)
    finally:
        tailer.stop()


def test_parser_tails_the_denied_fixture_as_a_live_file_emits_no_claims(tmp_path: Path) -> None:
    from witness.tailer import Tailer

    target = tmp_path / "session.jsonl"
    target.write_text("")
    events: list[AssistantClaim | TailMeta] = []
    tailer = Tailer([target], parser=ClaudeCodeClaimParser())
    tailer.start(lambda rec: events.append(rec))
    try:
        with open(target, "a") as fh:
            fh.write(DENIED_FIXTURE.read_text())
        import time

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            time.sleep(0.05)
        assert not any(isinstance(e, AssistantClaim) for e in events)
        assert not any(isinstance(e, TailMeta) and e.event == "parse_error" for e in events)
    finally:
        tailer.stop()
