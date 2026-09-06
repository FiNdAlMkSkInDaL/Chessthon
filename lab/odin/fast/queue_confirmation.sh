#!/bin/bash
set -euo pipefail
stage="$1"
dependency="$2"
lane="$3"
cpu="$4"
while systemctl --user is-active --quiet "$dependency"; do sleep 5; done
cd "$stage"
exec "$HOME/chess-tk/.venv/bin/python" -B -u lab/odin/fast/population.py --lane "$lane" --cpu "$cpu" --nodes 100000 --policy lab/odin/fast/finalist-policy.json --openings lab/odin/fast/generation-openings/confirm.fen --output lab/odin/fast/confirmation-results
