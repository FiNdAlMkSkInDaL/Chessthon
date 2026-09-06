#!/bin/bash
set -euo pipefail
stage="$1"
cpu="$2"
dependency="$3"
while systemctl --user is-active --quiet "$dependency"; do sleep 5; done
cd "$stage"
exec "$HOME/chess-tk/.venv/bin/python" -B -u -m lab.odin.release.native_gate --validation-root "$PWD" --harness-root "$PWD/lab/odin/official-harness-91f70e54" --archive "$PWD/candidate-linux-x86.zip" --cpu "$cpu" --cold-target 60 --odin-rules --output "$PWD/native-gate.json"
