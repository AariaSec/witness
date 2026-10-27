#!/usr/bin/env bash
# Honest small-n experiment harness for witness's real-agent claim.
#
# Runs every task under scripts/experiment/tasks/<name>/prompt.txt (optionally
# seeded from <name>/seed/*) REPEATS times each through a REAL Muse Code
# session (--provider meta --muse-arg --trust-workspace --muse-arg
# --disable-approval). Same discipline as every other real-agent run in this
# project: witness's own code never hardcodes a bypass flag — this script IS
# the operator choosing to supply it, explicitly, by running this file
# themselves. Not invoked by witness's own tooling, not run automatically.
#
# Each run gets a fresh lab dir and a fresh witness run_id. After each run,
# bundles it and appends one row to scripts/experiment/results.csv — so a
# crash partway through loses nothing already completed.
#
# Usage:
#   cd ~/Desktop/AariaSec/witness
#   bash scripts/experiment/run_batch.sh            # REPEATS=4 (32 runs)
#   REPEATS=3 bash scripts/experiment/run_batch.sh   # override
#
# Expected wall time: ~15-40 minutes for 32 runs (each run is a single short
# task, same shape as the flagship proof runs already done).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

REPEATS="${REPEATS:-4}"
EXP_DIR="$REPO_ROOT/scripts/experiment"
TASKS_DIR="$EXP_DIR/tasks"
RUNS_DIR="/tmp/witness-experiment-runs"
RESULTS_CSV="$EXP_DIR/results.csv"

mkdir -p "$RUNS_DIR"
if [ ! -f "$RESULTS_CSV" ]; then
  echo "run_id,task,task_type,repeat_idx,exit_code,findings,policy,stop_status" > "$RESULTS_CSV"
fi

export PATH="$HOME/.local/bin:$PATH"

task_type_of() {
  case "$1" in
    decoy_*) echo "decoy" ;;
    control_*) echo "control" ;;
    *) echo "unknown" ;;
  esac
}

run_one() {
  local task_name="$1" repeat_idx="$2"
  local task_dir="$TASKS_DIR/$task_name"
  local prompt
  prompt="$(cat "$task_dir/prompt.txt")"
  local task_type
  task_type="$(task_type_of "$task_name")"

  local lab="/tmp/witness-exp-lab-${task_name}-${repeat_idx}"
  rm -rf "$lab"
  mkdir -p "$lab"
  if [ -d "$task_dir/seed" ] && [ -n "$(ls -A "$task_dir/seed" 2>/dev/null)" ]; then
    cp -R "$task_dir/seed/." "$lab/"
  fi

  echo ""
  echo "=== [$task_name #$repeat_idx] ($task_type) ==="
  echo "$prompt"

  set +e
  OUTPUT="$(.venv/bin/python -m witness.cli record-muse "$prompt" \
    --lab "$lab" \
    --provider meta \
    --muse-arg --trust-workspace --muse-arg --disable-approval \
    --max-seconds 60 \
    --runs-dir "$RUNS_DIR" 2>&1)"
  RC=$?
  set -e
  echo "$OUTPUT"

  if [ $RC -ne 0 ]; then
    echo "$task_name-$repeat_idx,,$task_type,$repeat_idx,RECORD_FAILED,,," >> "$RESULTS_CSV"
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

  echo "$run_id,$task_name,$task_type,$repeat_idx,$VERIFY_RC,\"$findings\",$policy,$stop_status" >> "$RESULTS_CSV"
  echo ">>> verify exit=$VERIFY_RC findings=$findings policy=$policy"
}

TASK_NAMES=(decoy_webhook decoy_validate decoy_audit decoy_check control_docstring control_test control_readme control_refactor)

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
echo "Score with: .venv/bin/python scripts/experiment/score.py"
