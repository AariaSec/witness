#!/usr/bin/env bash
# judge_quickstart.sh -- one real session, end to end, in under a minute.
#
# Records a real AI-coding-agent-shaped session (sim_agent driving the exact
# same proxy/watcher/detector/ledger code every other claim in this repo is
# measured against -- see docs/CAPABILITY_MAP.md), signs and chain-verifies
# the resulting bundle (the actual merge-gate check, exit code and all), and
# opens the live hosted console so you can drag the real bundle.jsonl onto it
# yourself -- nothing is uploaded; it's parsed client-side in your own tab.
#
# No API key, no network except the recorder's own loopback-only marker/sink.
# Safe to run from a fresh clone.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=python3.11
command -v "$PY" >/dev/null 2>&1 || PY=python3

echo "== witness judge quickstart =="

if [ -d .venv ]; then
  echo "[1/4] Using existing .venv"
  BIN=.venv/bin
else
  echo "[1/4] Creating a venv and installing witness (first run only, ~20-30s)..."
  "$PY" -m venv .venv
  .venv/bin/pip install -q -e .
  BIN=.venv/bin
fi

echo "[2/4] Signing key (created once, reused after)..."
"$BIN/witness" keygen

echo "[3/4] Recording a real session -- decoy key read, decoy value exfiltrated, caught and stopped..."
DEMO_OUT="$("$BIN/witness" demo)"
echo "$DEMO_OUT"
BUNDLE="$(echo "$DEMO_OUT" | sed -n 's/^demo bundle: //p')"
if [ -z "$BUNDLE" ]; then
  echo "Could not parse the bundle path from: $DEMO_OUT" >&2
  exit 1
fi

echo "[4/4] Verifying the bundle -- hash chain, key whitelist, Ed25519 signature, policy gate..."
set +e
"$BIN/witness" verify "$BUNDLE"
VERIFY_EXIT=$?
set -e
echo "witness verify exit code: $VERIFY_EXIT (2 = policy FAIL, meaning a real stop-severity finding fired -- the catch worked)"

CONSOLE_URL="https://aariasec.github.io/witness/"
echo ""
echo "Opening the live console. Drag this file onto the page to replay it:"
echo "  $BUNDLE"
if [ -n "${WITNESS_QUICKSTART_NO_OPEN:-}" ]; then
  echo "(WITNESS_QUICKSTART_NO_OPEN set -- not launching a browser; URL is: $CONSOLE_URL)"
elif command -v open >/dev/null 2>&1; then
  open "$CONSOLE_URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$CONSOLE_URL"
else
  echo "Open this URL yourself: $CONSOLE_URL"
fi
