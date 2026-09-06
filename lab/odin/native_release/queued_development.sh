#!/bin/bash
set -euo pipefail
# Called from an immutable candidate stage. Wait for the current lane to free
# the CPU before cold measurement and games; never oversubscribe its wall clock.
stage="$1"
cpu="$2"
previous="$3"
cd "$stage"
while systemctl --user is-active --quiet "$previous"; do sleep 5; done
py="$HOME/chess-tk/.venv/bin/python"
"$py" -m lab.odin.release.native_gate --validation-root "$stage" --harness-root "$stage/lab/odin/official-harness-91f70e54" --archive "$stage/candidate-linux-x86.zip" --cpu "$cpu" --cold-target 60 --odin-rules --output "$stage/native-gate.json"
"$py" -u -m lab.odin.release.linux_match --validation-root "$stage" --harness-root "$stage/lab/odin/official-harness-91f70e54" --candidate "$stage/candidate-linux-x86.zip" --baseline "$stage/../control-r1/candidate-linux-x86.zip" --openings "$stage/lab/odin/release_openings/development.fen" --pairs 4 --opening-offset 0 --cpu "$cpu" --base-ms 60000 --increment-ms 500 --log "$stage/development.jsonl"
