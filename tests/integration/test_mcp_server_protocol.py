"""End-to-end MCP protocol test: spawns `witness.mcp_server` as a real
subprocess and talks to it over real stdio JSON-RPC via the official MCP
client SDK -- the same path Muse Code (or any MCP client) uses when it's
wired into `mcpServers` in settings.json. Unit-level tool-function tests
live in tests/unit/test_mcp_server.py; this file exists so "the server
actually speaks the protocol correctly" is verified too, not assumed.

`mcp` is an optional extra -- skip this file rather than fail collection
if it isn't installed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

import anyio  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_BUNDLE = str(REPO_ROOT / "runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl")


def _run(coro):  # type: ignore[no-untyped-def]
    return anyio.run(lambda: coro)


async def _list_tools_and_call() -> tuple[list[str], str]:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "witness.mcp_server"], cwd=str(REPO_ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool(
                "witness_verify_bundle", {"bundle_path": _REAL_BUNDLE}
            )
            text = result.content[0].text if result.content else ""
            return [t.name for t in tools.tools], text


def test_server_advertises_all_three_tools_over_real_stdio() -> None:
    names, _ = _run(_list_tools_and_call())
    assert set(names) == {
        "witness_verify_bundle",
        "witness_list_findings",
        "witness_check_tree_coverage",
    }


def test_real_tool_call_over_real_stdio_returns_correct_result() -> None:
    _, text = _run(_list_tools_and_call())
    assert '"ok": true' in text.lower() or '"ok":true' in text.lower().replace(" ", "")
    assert '"policy": "PASS"' in text or '"policy":"PASS"' in text.replace(" ", "")
