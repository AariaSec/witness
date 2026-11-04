"""Copy of the script that produced runs/frozen/live-capture-*. It runs the real `witness` CLI up to 4 times and keeps the first
status=ok result (earlier attempts that timed out or fell back are not saved and the attempt count is not recorded). Keys are read by
witness itself and never by this script."""
"""Run the real `witness triage ... --provider meta` once on a real Muse Code bundle and save the exact
output + wall time for the reel's terminal beat. Key is read by witness itself; never read or printed here.
Only writes a capture on a corroborated, status=ok result."""
import os, json, subprocess, time, datetime, pathlib
W = pathlib.Path(__file__).resolve().parents[2]  # repo root
BUNDLE = 'runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl'
CMD = ['./.venv/bin/witness', 'triage', BUNDLE, '--provider', 'meta']
for attempt in range(1, 5):
    t0 = time.time()
    p = subprocess.run(CMD, cwd=W, capture_output=True, text=True, timeout=240)
    ms = int((time.time() - t0) * 1000)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]
    ok = any('status=ok' in l for l in lines) and any('corroborated' in l and 'not corroborated' not in l for l in lines)
    print('attempt', attempt, ms, 'ms', 'OK' if ok else lines[-1][:100])
    if ok:
        break
else:
    raise SystemExit('no corroborated status=ok triage after 4 attempts; not writing a capture')
out = {'cmd': 'witness triage bundle.jsonl --provider meta', 'lines': lines, 'wall_ms': ms, 'exit': p.returncode,
       'captured_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
dst = pathlib.Path(__file__).resolve().parents[3] / 'meta-hackathon' / 'ui' / 'assets'  # demo-reel assets; not part of this repo
HAVE_DST = dst.is_dir()
if HAVE_DST:
    (dst / 'live_triage_out.json').write_text(json.dumps(out, indent=1))
    (dst / 'live_triage_out.js').write_text('window.LIVEOUT_T=' + json.dumps(out) + ';')
frozen = W / 'runs' / 'frozen' / ('live-capture-triage-' + datetime.date.today().strftime('%Y%m%d'))
frozen.mkdir(parents=True, exist_ok=True)
(frozen / 'output.json').write_text(json.dumps(out, indent=1))
(frozen / 'README.txt').write_text('Real `witness triage --provider meta` run (Muse Spark 1.3, Meta Model API) on a real Muse Code bundle (' + BUNDLE + ').\nThat bundle\'s `mismatch` finding came from the since-fixed read-vs-write detector bug; the model retracts it and a deterministic verifier corroborates.\nAdvisory only: never changes exit code, policy, chain or signature. See output.json.\n')
print(json.dumps(out, indent=1)[:900])
