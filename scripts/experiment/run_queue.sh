#!/usr/bin/env bash
# FROZEN driver for the unprompted real-agent experiment. Read it once; it does not change overnight.
#
# What is data (re-read before EVERY run, so it can be edited while this is running):
#   scripts/experiment/queue.txt            which "task repeat_idx" to run next (done items are in queue.done)
#   scripts/experiment/tasks_unprompted/*   the task folders: prompt.txt, seed/, pull_level.txt
# What is fixed (this file): how Muse Code is launched. The approval-bypass flags below are supplied HERE, by
# the operator who chooses to run this file; witness's own code never sets them and nothing starts this automatically.
#
#   cd ~/Desktop/AariaSec/witness && bash scripts/experiment/run_queue.sh
#   touch scripts/experiment/STOP        # finish the current run, then stop
#   DRYRUN=1 bash scripts/experiment/run_queue.sh   # print the next items without launching anything
# Appends one row per run to results_unprompted.csv; exits after 40 minutes with an empty queue.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
EXP="$REPO_ROOT/scripts/experiment"
QUEUE="$EXP/queue.txt"; DONE="$EXP/queue.done"; STOPF="$EXP/STOP"
TASKS_DIR="$EXP/tasks_unprompted"; RESULTS_CSV="$EXP/results_unprompted.csv"
RUNS_DIR="/tmp/witness-experiment-runs-unprompted"
mkdir -p "$RUNS_DIR"; touch "$DONE"
[ -f "$RESULTS_CSV" ] || echo "run_id,task,pull_level,repeat_idx,exit_code,findings,policy,stop_status,marker_peers" > "$RESULTS_CSV"
export PATH="$HOME/.local/bin:$PATH"

next_item() {  # first queue line (task idx) that is not in queue.done and whose task folder exists
  while read -r task idx _; do
    case "$task" in ''|\#*) continue ;; esac
    grep -qxF "$task $idx" "$DONE" && continue
    [ -f "$TASKS_DIR/$task/prompt.txt" ] || continue
    echo "$task $idx"; return 0
  done < "$QUEUE"
  return 1
}

run_one() {
  local task_name="$1" repeat_idx="$2" task_dir="$TASKS_DIR/$1"
  local pull; pull="$(cat "$task_dir/pull_level.txt" 2>/dev/null || echo unknown)"
  local prompt; prompt="$(cat "$task_dir/prompt.txt")"
  local lab="/tmp/witness-expu-lab-${task_name}-${repeat_idx}"
  rm -rf "$lab"; mkdir -p "$lab"; [ -d "$task_dir/seed" ] && cp -R "$task_dir/seed/." "$lab/"
  echo; echo "=== [$task_name #$repeat_idx] ($pull) ==="; echo "$prompt"
  OUTPUT="$(.venv/bin/python -m witness.cli record-muse "$prompt" --lab "$lab" --provider meta \
    --muse-arg --trust-workspace --muse-arg --disable-approval --max-seconds 150 \
    --runs-dir "$RUNS_DIR" 2>&1)"
  RC=$?
  echo "$OUTPUT" | tail -3
  if [ $RC -ne 0 ]; then echo "$task_name-$repeat_idx,,$pull,$repeat_idx,RECORD_FAILED,,,," >> "$RESULTS_CSV"; return; fi
  local run_dir; run_dir="$(echo "$OUTPUT" | grep '^recorded:' | awk '{print $2}')"
  local run_id; run_id="$(basename "$run_dir")"
  .venv/bin/python -m witness.cli bundle "$run_dir" --out "$run_dir/bundle.jsonl" >/dev/null 2>&1
  VERIFY_OUT="$(.venv/bin/python -m witness.cli verify "$run_dir/bundle.jsonl" 2>&1)"; VERIFY_RC=$?
  local findings policy extra
  findings="$(echo "$VERIFY_OUT" | grep -o "findings={[^}]*}" | head -1 | sed 's/findings=//; s/"/""/g')"
  policy="$(echo "$VERIFY_OUT" | grep -o "policy: [A-Z]*" | head -1 | sed 's/policy: //')"
  extra="$(.venv/bin/python - "$run_dir/bundle.jsonl" <<'PY'
import json, sys
stop = peers = ""
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r.get("kind") == "receipt":
        stop = r["body"]["stop_status"]
    if r.get("kind") == "marker_read":
        peers += ("" if not peers else "|") + str(r.get("peer_exe"))
print(stop + "," + peers)
PY
)"
  echo "$run_id,$task_name,$pull,$repeat_idx,$VERIFY_RC,\"$findings\",$policy,$extra" >> "$RESULTS_CSV"
  echo ">>> $task_name #$repeat_idx verify exit=$VERIFY_RC policy=$policy findings=$findings"
}

idle=0
while true; do
  [ -f "$STOPF" ] && { echo "STOP file found; exiting."; exit 0; }
  if item="$(next_item)"; then
    idle=0
    set -- $item
    if [ -n "${DRYRUN:-}" ]; then echo "DRYRUN next: $item"; echo "$item" >> "$DONE"; continue; fi
    run_one "$1" "$2"
    echo "$item" >> "$DONE"
  else
    idle=$((idle+1)); [ "$idle" -ge 80 ] && { echo "queue empty for 40 min; exiting."; exit 0; }
    [ -n "${DRYRUN:-}" ] && { echo "DRYRUN: queue empty"; exit 0; }
    sleep 30
  fi
done
