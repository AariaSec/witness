"""Record REAL runs of witness commands in a pseudo-terminal, with real output timing, for the reel's
terminal beat. Each command is executed for real (live Meta calls); nothing is typed or faked. Output is
stored as timed chunks (like an asciinema cast). Keys are read by witness itself; never read or printed here.
A capture is kept only if the run's output shows `status=ok` (so a fallback is never presented as live), and
the attempt count is written next to the capture."""
import json, os, pty, select, subprocess, sys, time, datetime, pathlib
W = pathlib.Path('/Users/aj/Desktop/AariaSec/witness')
OUT = pathlib.Path(__file__).parent / 'ui' / 'assets'
BUNDLE_SIM = 'runs/frozen/analyst-live-proof-20261026-145221-6150/bundle.jsonl'
BUNDLE_REAL = 'runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl'
WIT = './.venv/bin/witness'
JOBS = [
    ('meta',    'witness verify bundle.jsonl --with-analyst --analyst-provider meta',    [WIT, 'verify', BUNDLE_SIM, '--with-analyst', '--analyst-provider', 'meta'],    'status=ok'),
    ('glimmer', 'witness verify bundle.jsonl --with-analyst --analyst-provider glimmer', [WIT, 'verify', BUNDLE_SIM, '--with-analyst', '--analyst-provider', 'glimmer'], 'status=ok'),
    ('triage',  'witness triage bundle.jsonl --provider meta',                          [WIT, 'triage', BUNDLE_REAL, '--provider', 'meta'],                              'status=ok'),
]
def run(cmd, tmax=240):
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(W); os.environ['TERM'] = 'xterm'; os.execv(cmd[0], cmd)
    t0 = time.time(); chunks = []; buf = b''
    while True:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try: d = os.read(fd, 4096)
            except OSError: break
            if not d: break
            chunks.append([round(time.time() - t0, 3), d.decode('utf-8', 'replace')])
        if time.time() - t0 > tmax: os.kill(pid, 9); break
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
            if done:
                try:
                    while True:
                        d = os.read(fd, 4096)
                        if not d: break
                        chunks.append([round(time.time() - t0, 3), d.decode('utf-8', 'replace')])
                except OSError: pass
                break
        except ChildProcessError: break
    return round(time.time() - t0, 3), chunks
casts = []
for name, shown, cmd, need in JOBS:
    for attempt in range(1, 5):
        wall, chunks = run(cmd)
        text = ''.join(c[1] for c in chunks)
        ok = need in text
        print(name, 'attempt', attempt, round(wall, 1), 's', 'OK' if ok else 'not ok')
        if ok: break
    else:
        raise SystemExit(f'{name}: no status=ok after 4 attempts; not writing a capture')
    casts.append({'name': name, 'cmd': shown, 'wall_s': wall, 'attempts_used': attempt, 'chunks': chunks,
                  'bundle': 'simulated-scenario bundle' if name != 'triage' else 'real Muse Code session'})
out = {'captured_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'casts': casts}
(OUT / 'live_pty.json').write_text(json.dumps(out))
(OUT / 'live_pty.js').write_text('window.LIVEPTY=' + json.dumps(out) + ';')
frozen = W / 'runs' / 'frozen' / ('live-capture-pty-' + datetime.date.today().strftime('%Y%m%d'))
frozen.mkdir(parents=True, exist_ok=True)
(frozen / 'casts.json').write_text(json.dumps(out, indent=1))
(frozen / 'README.txt').write_text('Real pseudo-terminal recordings (timed output chunks) of three witness commands with live Meta-model calls, for the demo video.\nEach command was executed for real; a capture is kept only if its output contains status=ok (attempts used are in casts.json).\nBundles: calls 1-2 on a recorded scripted-scenario bundle (simulated: true); triage on a real Muse Code bundle.\nSee scripts/capture/capture_live_pty.py.\n')
print('saved', [(c['name'], c['wall_s'], c['attempts_used']) for c in casts])
