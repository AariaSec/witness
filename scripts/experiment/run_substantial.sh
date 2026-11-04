#!/usr/bin/env bash
# Substantial real-agent sessions — multi-file, multi-step coding tasks, not
# the 60-second micro-tasks in scripts/experiment/tasks/. Built because the
# original experiment (honest, but cheap to run) left Meta Model API spend
# near zero; this generates genuinely larger sessions (several minutes each,
# multiple files, tests run and verified) through the SAME proven harness
# (`witness.cli record-muse`, real Muse Code, `--provider meta`), useful both
# as a bigger demo artifact and as real usage of the Meta Model API credits.
#
# Entirely additive: separate tasks dir (tasks_substantial/), separate
# results file (results_substantial.csv), separate runs dir. Does not touch
# or re-run the original locked experiment (run_batch.sh / results.csv).
#
# Usage:
#   cd ~/Desktop/AariaSec/witness
#   bash scripts/experiment/run_substantial.sh                     # REPEATS=3, effort=ultra
#   REPEATS=10 bash scripts/experiment/run_substantial.sh           # override repeats
#   REASONING_EFFORT=high REPEATS=10 bash scripts/experiment/run_substantial.sh
#   MUSE_MODEL=muse-wonder REPEATS=10 bash scripts/experiment/run_substantial.sh
#
# A single-task pilot at default (high) effort took ~54s wall clock and
# produced a full feature + tests + README update, verified clean. Effort is
# forced to `ultra` (Meta's highest reasoning tier, via --muse-arg
# --reasoning-effort) by default specifically to use more real tokens per
# call — override with REASONING_EFFORT if that's not wanted.
#
# Confirmed by watching the Meta Model API billing dashboard in real time
# (2026-10-27): there is NO lag — it decrements by a few cents per run, not
# otherwise. The default model (muse-spark-1.3) is just genuinely cheap per
# session even at ultra effort. MUSE_MODEL lets you point the agent itself at
# a pricier catalog model (e.g. `muse-wonder`, the premium hosted model,
# vs. the free/open muse-spark-open the analyst pass already uses
# separately) for runs where real, visible spend matters. The separate
# analyst pass (`witness verify --with-analyst`) bills through Baseten, a
# third-party host with its own account — it will NEVER move the Meta Model
# API dashboard number, regardless of how many times it runs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

REPEATS="${REPEATS:-3}"
MAX_SECONDS="${MAX_SECONDS:-480}"
EXP_DIR="$REPO_ROOT/scripts/experiment"
TASKS_DIR="$EXP_DIR/tasks_substantial"
RUNS_DIR="/tmp/witness-substantial-runs"
RESULTS_CSV="$EXP_DIR/results_substantial.csv"

mkdir -p "$RUNS_DIR"
if [ ! -f "$RESULTS_CSV" ]; then
  echo "run_id,task,task_type,repeat_idx,exit_code,findings,policy,stop_status" > "$RESULTS_CSV"
fi

export PATH="$HOME/.local/bin:$PATH"

task_type_of() {
  case "$1" in
    *decoy*) echo "decoy" ;;
    *) echo "control" ;;
  esac
}

run_one() {
  local task_name="$1" repeat_idx="$2"
  local task_dir="$TASKS_DIR/$task_name"
  local prompt
  prompt="$(cat "$task_dir/prompt.txt")"
  local task_type
  task_type="$(task_type_of "$task_name")"

  local lab="/tmp/witness-sub-lab-${task_name}-${repeat_idx}"
  rm -rf "$lab"
  mkdir -p "$lab"
  if [ -d "$task_dir/seed" ] && [ -n "$(ls -A "$task_dir/seed" 2>/dev/null)" ]; then
    cp -R "$task_dir/seed/." "$lab/"
  fi

  echo ""
  echo "=== [$task_name #$repeat_idx] ($task_type) ==="
  echo "$prompt"

  local -a model_args=()
  if [ -n "${MUSE_MODEL:-}" ]; then
    model_args=(--muse-arg --model --muse-arg "$MUSE_MODEL")
  fi

  set +e
  OUTPUT="$(.venv/bin/python -m witness.cli record-muse "$prompt" \
    --lab "$lab" \
    --provider meta \
    --muse-arg --trust-workspace --muse-arg --disable-approval \
    --muse-arg --reasoning-effort --muse-arg "${REASONING_EFFORT:-ultra}" \
    ${model_args[@]+"${model_args[@]}"} \
    --max-seconds "$MAX_SECONDS" \
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

TASK_NAMES=(substantial_feature_build substantial_refactor substantial_decoy_integration)

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
echo "Bundles are under $RUNS_DIR/<run_id>/bundle.jsonl — pick the richest one for the demo."
