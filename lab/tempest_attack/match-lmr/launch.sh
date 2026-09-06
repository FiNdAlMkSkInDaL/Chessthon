#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-attack-lmr-r1"
PY="$HOME/chess-tk/.venv/bin/python"
"$PY" -B lab/tempest_attack/match-lmr/clock_match.py --candidate lab/tempest_attack/prototypes/pawn_lmr --baseline tempest_exact --cpu 0 --think-ms 500 --indices 0,1,2,3 --openings lab/odin/fast/generation-openings/screen.fen --output lab/tempest_attack/match-lmr/lane-a.jsonl > lab/tempest_attack/match-lmr/lane-a.stdout 2> lab/tempest_attack/match-lmr/lane-a.stderr &
A=$!
"$PY" -B lab/tempest_attack/match-lmr/clock_match.py --candidate lab/tempest_attack/prototypes/pawn_lmr --baseline tempest_exact --cpu 1 --think-ms 500 --indices 4,5,6,7 --openings lab/odin/fast/generation-openings/screen.fen --output lab/tempest_attack/match-lmr/lane-b.jsonl > lab/tempest_attack/match-lmr/lane-b.stdout 2> lab/tempest_attack/match-lmr/lane-b.stderr &
B=$!
wait "$A"
wait "$B"
