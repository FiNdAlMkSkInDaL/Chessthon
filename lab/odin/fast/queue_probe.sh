#!/bin/bash
set -euo pipefail
stage="$1"
dependency="$2"
while systemctl --user is-active --quiet "$dependency"; do sleep 5; done
cd "$stage"
exec "$HOME/chess-tk/.venv/bin/python" -B -u lab/odin/new_games/probe_odin.py --source odin_v6_guards --cpu 1 --roots lab/odin/new_games/native-diagnostic-roots.json --output lab/odin/fast/probe-guards.jsonl
