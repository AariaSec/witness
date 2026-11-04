"""Copy of the script that produced runs/frozen/live-capture-*. It runs the real `witness` CLI up to 4 times and keeps the first
status=ok result (earlier attempts that timed out or fell back are not saved and the attempt count is not recorded). Keys are read by
witness itself and never by this script."""
"""Run the real `witness verify --with-analyst --analyst-provider meta` once and
save the exact output + wall time for the reel's terminal beat. The key is read
by witness itself (META_API_KEY or ~/.config/aariasec/meta_api_key); this script
never reads or prints it."""
import json, subprocess, time, datetime, pathlib
import os
if not os.environ.get('WITNESS_GLIMMER_URL'):
    raise SystemExit('set WITNESS_GLIMMER_URL to your own deployed Glimmer endpoint (see scripts/glimmer_modal.py)')
W = pathlib.Path(__file__).resolve().parents[2]  # repo root
BUNDLE = 'runs/frozen/analyst-live-proof-20261026-145221-6150/bundle.jsonl'
CMD = ['./.venv/bin/witness', 'verify', BUNDLE, '--with-analyst', '--analyst-provider', 'glimmer']
for attempt in range(1, 5):
    t0 = time.time()
    p = subprocess.run(CMD, cwd=W, capture_output=True, text=True, timeout=420)
    ms = int((time.time() - t0) * 1000)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]
    status = next((l for l in lines if l.startswith('analyst:')), '')
    print('attempt', attempt, ms, 'ms', status[:60])
    if 'status=ok' in status:
        break
else:
    raise SystemExit('no live status=ok after 4 attempts; not writing a fake-live capture')
out = {
    'cmd': 'witness verify bundle.jsonl --with-analyst --analyst-provider glimmer',
    'lines': lines, 'wall_ms': ms, 'exit': p.returncode,
    'captured_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
}
dst = pathlib.Path(__file__).resolve().parents[3] / 'meta-hackathon' / 'ui' / 'assets'  # demo-reel assets; not part of this repo
HAVE_DST = dst.is_dir()
if HAVE_DST:
    (dst / 'live_glimmer_out.json').write_text(json.dumps(out, indent=1))
    (dst / 'live_glimmer_out.js').write_text('window.LIVEOUT=' + json.dumps(out) + ';')
frozen = W / 'runs' / 'frozen' / ('live-capture-glimmer-' + datetime.date.today().strftime('%Y%m%d'))
frozen.mkdir(parents=True, exist_ok=True)
(frozen / 'output.json').write_text(json.dumps(out, indent=1))
(frozen / 'README.txt').write_text('Real `witness verify --with-analyst --analyst-provider meta` run (Muse Glimmer 30B, own hardware on Modal (A10G)) captured for the demo video.\nBundle: ' + BUNDLE + '\nSee output.json for the exact output, wall time and timestamp. Content-free: codes/counts only.\n')
print(json.dumps(out, indent=1)[:1100])
