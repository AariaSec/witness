"""Record a REAL MCP client session against witness's real MCP server (stdio JSON-RPC, official SDK client):
initialize, tools/list, then tools/call witness_verify_bundle and witness_list_findings on the real README-setup bundle.
Output is the actual responses, with real timing, stored as timed chunks like the pty casts. The client is a plain MCP
client (the same path any MCP client takes, including Muse Code when wired into mcpServers); this is NOT a recording of
Muse Code itself."""
import anyio, json, sys, time, datetime, pathlib
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
W = pathlib.Path('/Users/aj/Desktop/AariaSec/witness')
BUNDLE = 'runs/frozen/unprompted-experiment-20261103/20261103-231501-9019/bundle.jsonl'
chunks = []; t0 = None
def say(text):
    chunks.append([round(time.time() - t0, 3), text + '\n'])
def short(obj, n=400):
    s = json.dumps(obj, separators=(', ', ': '))
    return s if len(s) <= n else s[:n] + ' …'
async def main():
    global t0
    params = StdioServerParameters(command=str(W / '.venv/bin/python'), args=['-m', 'witness.mcp_server'], cwd=str(W))
    t0 = time.time()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize(); say('initialize  ->  ok (server: witness, stdio)')
            tools = await s.list_tools(); say('tools/list  ->  ' + ', '.join(t.name for t in tools.tools))
            say('tools/call witness_verify_bundle {"bundle_path": "bundle.jsonl"}')
            r = await s.call_tool('witness_verify_bundle', {'bundle_path': BUNDLE})
            d = json.loads(r.content[0].text); say('  ->  ' + short({k: d[k] for k in d if k in ('receipt_ok', 'policy', 'stop_findings', 'records', 'findings', 'receipt_status')}))
            say('tools/call witness_list_findings {"bundle_path": "bundle.jsonl"}')
            r2 = await s.call_tool('witness_list_findings', {'bundle_path': BUNDLE})
            items = []
            for c in r2.content:
                try:
                    v = json.loads(c.text)
                except Exception:
                    continue
                items += v if isinstance(v, list) else [v]
            for f in items[:12]:
                say('  ->  ' + short({k: f[k] for k in f if k in ('seq', 'fkind', 'kind', 'severity', 'evidence_seqs')}, 160))
    return time.time() - t0
wall = anyio.run(main)
cast = {'name': 'mcp', 'cmd': 'MCP client -> python -m witness.mcp_server (stdio)', 'wall_s': round(wall, 2), 'attempts_used': 1,
        'chunks': chunks, 'bundle': 'real README-setup session'}
out = {'captured_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'casts': [cast]}
dst = pathlib.Path(__file__).parent / 'ui' / 'assets'
(dst / 'live_mcp.js').write_text('window.LIVEMCP=' + json.dumps(out) + ';')
fr = W / 'runs' / 'frozen' / 'live-capture-mcp-20261104'; fr.mkdir(parents=True, exist_ok=True)
(fr / 'casts.json').write_text(json.dumps(out, indent=1))
(fr / 'README.txt').write_text('Real MCP client session (official MCP SDK client over stdio) against witness\'s real MCP server, on the real README-setup bundle. Responses and timing are as received. This is a plain MCP client, not a recording of Muse Code. See scripts/capture/capture_mcp.py.\n')
print(''.join(c[1] for c in chunks)); print('wall', cast['wall_s'])
