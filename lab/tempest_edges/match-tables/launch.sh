#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-edges-bundles-r1"
"$HOME/chess-tk/.venv/bin/python" -B lab/tempest_edges/match-tables/clock_match.py --candidate lab/tempest_edges/prototypes/tables_guard --baseline lab/tempest_edges/prototypes/release --cpu 1 --think-ms 500 --indices 0,1,2,3,4,5,6,7 --openings lab/odin/fast/generation-openings/screen.fen --output lab/tempest_edges/match-tables/lane.jsonl > lab/tempest_edges/match-tables/lane.stdout 2> lab/tempest_edges/match-tables/lane.stderr
