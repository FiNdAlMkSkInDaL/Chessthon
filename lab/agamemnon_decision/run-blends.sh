#!/bin/sh
set -eu
cpu="$1"
while systemctl --user is-active --quiet "agamemnon-settled-match-$cpu.service"; do sleep 5; done
if [ "$cpu" = 0 ]; then variants='blend25a blend15 blend30'; else variants='blend20 blend35 blend25b'; fi
for variant in $variants; do
    "$HOME/chess-tk/.venv/bin/python" "$HOME/chess-sign-odin-20260905/agamemnon-decision/probe.py" --variant "$variant" --cpu "$cpu"
done
