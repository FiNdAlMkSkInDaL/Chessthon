#!/bin/sh
set -eu
cpu="$1"
if [ "$cpu" = 0 ]; then lane=a; else lane=b; fi
cd "$HOME/chess-sign-odin-20260905/agamemnon-confirm-replay25"
exec "$HOME/chess-tk/.venv/bin/python" -B -u -m lab.odin.release.linux_match \
    --validation-root "$PWD" --harness-root "$PWD/lab/tempest_build/official-284724ab" \
    --candidate candidate-linux-x86.zip --baseline baseline-tempest.zip \
    --plan confirmation24/plan.json --suite confirmation --lane "$lane" \
    --cpu "$cpu" --openings confirmation24/openings.fen --log "confirmation24/lane-$lane.jsonl"
