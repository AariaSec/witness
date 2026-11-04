#!/usr/bin/env bash
# Large-context real-agent sessions — tasks that require reading a genuinely
# large amount of real code (witness's own src/ and tests/, ~15k lines
# combined) in a single session, through the SAME proven harness
# (`witness.cli record-muse`, real Muse Code, `--provider meta`).
#
# Why this exists: the 60-second micro-tasks (tasks/) and the multi-file
# feature-build tasks (tasks_substantial/) both confirmed real spend is only
# a few cents per run regardless of reasoning-effort tier or task repeats —
# input token volume (how much the agent has to actually read), not output
# or effort, is the real cost driver. These tasks force reading ~5k-15k
# lines of real code per session, which is the best honest lever available
# given this hackathon key has no access to a pricier model (muse-wonder /
# muse-wonder-1 both 404 "does not exist or you lack access").
#
# Bonus: the output (an architecture doc, a real test-gap audit) is genuinely
# useful, not just a spend exercise — worth reading the results either way.
#
# Entirely additive: separate tasks dir (tasks_large_context/), separate
# results file (results_large_context.csv), separate runs dir.
#
# Usage:
#   cd ~/Desktop/AariaSec/witness
#   bash scripts/experiment/run_large_context.sh                    # REPEATS=2
#   REPEATS=5 bash scripts/experiment/run_large_context.sh          # override

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

REPEATS="${REPEATS:-2}"
MAX_SECONDS="${MAX_SECONDS:-900}"
EXP_DIR="$REPO_ROOT/scripts/experiment"
TASKS_DIR="$EXP_DIR/tasks_large_context"
RUNS_DIR="/tmp/witness-large-context-runs"
RESULTS_CSV="$EXP_DIR/results_large_context.csv"

mkdir -p "$RUNS_DIR"
if [ ! -f "$RESULTS_CSV" ]; then
  echo "run_id,task,repeat_idx,exit_code,findings,policy,stop_status" > "$RESULTS_CSV"
fi

export PATH="$HOME/.local/bin:$PATH"

run_one() {
  local task_name="$1" repeat_idx="$2"
  local task_dir="$TASKS_DIR/$task_name"
  local prompt
  prompt="$(cat "$task_dir/prompt.txt")"

  local lab="/tmp/witness-lc-lab-${task_name}-${repeat_idx}"
  rm -rf "$lab"
  mkdir -p "$lab"
  cp -R "$task_dir/seed/." "$lab/"

  echo ""
  echo "=== [$task_name #$repeat_idx] ==="

  set +e
  OUTPUT="$(.venv/bin/python -m witness.cli record-muse "$prompt" \
    --lab "$lab" \
    --provider meta \
    --muse-arg --trust-workspace --muse-arg --disable-approval \
    --muse-arg --reasoning-effort --muse-arg "${REASONING_EFFORT:-ultra}" \
    --max-seconds "$MAX_SECONDS" \
    --runs-dir "$RUNS_DIR" 2>&1)"
  RC=$?
  set -e
  echo "$OUTPUT"

  if [ $RC -ne 0 ]; then
    echo "$task_name-$repeat_idx,,$repeat_idx,RECORD_FAILED,,," >> "$RESULTS_CSV"
    return
  fi

  local run_dir
  run_dir="$(echo "$OUTPUT" | grep '^recorded:' | awk '{print $2}')"
  local run_id
  run_id="$(basename "$run_dir")"

  .venv/bin/python -m witness.cli bundle "$run_dir" --out "$run_dir/bundle.jsonl" >/dev/null 2>&1

  set +e
  VERIFY_OUT="$(.venv/bin/python -m witness.cli verify "$run_dir/bundle.jsonl" 2>&1)"
  VERIFY_RC=$?
  set -e

  local findings policy stop_status
  findings="$(echo "$VERIFY_OUT" | grep -o "findings={[^}]*}" | head -1 | sed 's/findings=//; s/"/""/g')"
  policy="$(echo "$VERIFY_OUT" | grep -o "policy: [A-Z]*" | head -1 | sed 's/policy: //')"
  stop_status="$(python3 -c "
import json
try:
    with open('$run_dir/bundle.jsonl') as f:
        for line in f:
            r = json.loads(line)
            if r.get('kind') == 'receipt':
                print(r['body']['stop_status'])
                break
except Exception:
    print('')
")"

  echo "$run_id,$task_name,$repeat_idx,$VERIFY_RC,\"$findings\",$policy,$stop_status" >> "$RESULTS_CSV"
  echo ">>> verify exit=$VERIFY_RC findings=$findings policy=$policy"
  echo ">>> output doc(s): $(find "$lab" -maxdepth 1 -name '*.md' -newer "$task_dir/prompt.txt" 2>/dev/null | tr '\n' ' ')"
}

TASK_NAMES=(large_context_architecture_doc large_context_test_gap_audit)

total=$(( ${#TASK_NAMES[@]} * REPEATS ))
n=0
for task_name in "${TASK_NAMES[@]}"; do
  for i in $(seq 1 "$REPEATS"); do
    n=$((n+1))
    echo ""
    echo "######## run $n / $total ########"
    run_one "$task_name" "$i"
  done
done

echo ""
echo "Done. $total runs attempted. Results: $RESULTS_CSV"
echo "Labs (with the real output docs) are under /tmp/witness-lc-lab-<task>-<n>/"
