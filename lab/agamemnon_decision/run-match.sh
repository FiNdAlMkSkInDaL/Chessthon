#!/bin/sh
set -eu
cpu="$1"
# One active mover per CPU. Continue this authorized pipeline after its diagnostic lane.
while systemctl --user is-active --quiet "agamemnon-decision-models-$cpu.service"; do
    sleep 5
done
cd "$HOME/chess-sign-odin-20260905"
if [ "$cpu" = 0 ]; then indices='0,1,2,3'; else indices='4,5,6,7'; fi
exec "$HOME/chess-tk/.venv/bin/python" lab/agamemnon_scale/match-backed-mixed25/clock_match.py \
    --candidate lab/agamemnon_decision/native/mixed25 --baseline tempest_exact \
    --cpu "$cpu" --think-ms 500 --indices "$indices" \
    --openings lab/odin/fast/generation-openings/screen.fen \
    --output "lab/agamemnon_scale/match-backed-mixed25/lane$cpu.jsonl"
