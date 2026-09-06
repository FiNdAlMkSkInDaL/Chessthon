#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-stack-r1"
PY="$HOME/chess-tk/.venv/bin/python"
(for V in narrow lazy packed both; do taskset -c 0 "$PY" -B lab/tempest_stack/bench.py --variant "$V" --lane a; done) > lab/tempest_stack/lane-a.stdout 2> lab/tempest_stack/lane-a.stderr &
A=$!
(for V in both packed lazy narrow; do taskset -c 1 "$PY" -B lab/tempest_stack/bench.py --variant "$V" --lane b; done) > lab/tempest_stack/lane-b.stdout 2> lab/tempest_stack/lane-b.stderr &
B=$!
RA=0; RB=0
wait "$A" || RA=$?
wait "$B" || RB=$?
test "$RA" -eq 0 && test "$RB" -eq 0
