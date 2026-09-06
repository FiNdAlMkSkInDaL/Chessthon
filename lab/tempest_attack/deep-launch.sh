#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-attack-lmr-r1"
PY="$HOME/chess-tk/.venv/bin/python"
for V in baseline pawn_lmr; do
 taskset -c 1 "$PY" -B lab/tempest_attack/trace_search_v5.py --variant "$V" --cpu 1 --cases lab/tempest_attack/deep-cases.json --tag linux-deep
done
