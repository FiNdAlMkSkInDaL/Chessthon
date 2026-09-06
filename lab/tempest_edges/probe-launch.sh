#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-edges-probe-r1"
PY="$HOME/chess-tk/.venv/bin/python"
"$PY" -B lab/tempest_edges/probe.py --variant control --cpu 0 --cases lab/tempest_edges/tt-cases.json --tag tt-linux > lab/tempest_edges/tt-a.stdout 2> lab/tempest_edges/tt-a.stderr &
A=$!
"$PY" -B lab/tempest_edges/probe.py --variant tt_instrument --cpu 1 --cases lab/tempest_edges/tt-cases.json --tag tt-linux > lab/tempest_edges/tt-b.stdout 2> lab/tempest_edges/tt-b.stderr &
B=$!
RA=0; RB=0
wait "$A" || RA=$?
wait "$B" || RB=$?
test "$RA" -eq 0 && test "$RB" -eq 0
