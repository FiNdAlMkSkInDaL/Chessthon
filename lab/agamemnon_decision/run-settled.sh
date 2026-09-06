#!/bin/sh
set -eu
cpu="$1"
while systemctl --user is-active --quiet "agamemnon-backed-match-$cpu.service"; do sleep 5; done
if [ "$cpu" = 0 ]; then variant='settled-pair25'; else variant='settled-pair50'; fi
exec "$HOME/chess-tk/.venv/bin/python" "$HOME/chess-sign-odin-20260905/agamemnon-decision/probe.py" --variant "$variant" --cpu "$cpu"
