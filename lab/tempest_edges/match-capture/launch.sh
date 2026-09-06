#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-edges-matches-r1"
"$HOME/chess-tk/.venv/bin/python" -B lab/tempest_edges/match-capture/clock_match.py --candidate lab/tempest_edges/prototypes/capture --baseline lab/tempest_edges/prototypes/control --cpu 8 --think-ms 500 --indices 0,1,2,3,4,5,6,7 --openings lab/odin/fast/generation-openings/screen.fen --output lab/tempest_edges/match-capture/lane.jsonl > lab/tempest_edges/match-capture/lane.stdout 2> lab/tempest_edges/match-capture/lane.stderr
