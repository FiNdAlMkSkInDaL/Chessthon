#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-edges-bundles-r1"
bash lab/tempest_edges/match-bundle/launch.sh &
A=$!
bash lab/tempest_edges/match-tables/launch.sh &
B=$!
RA=0; RB=0
wait "$A" || RA=$?
wait "$B" || RB=$?
test "$RA" -eq 0 && test "$RB" -eq 0
