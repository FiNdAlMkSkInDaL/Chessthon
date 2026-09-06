#!/bin/sh
set -eu
cd "$HOME/chess-sign-odin-20260905/agamemnon-frontier"
cpu="$1"
if [ "$cpu" = 0 ]; then
  variants='tempest mix25 rank relative50'
else
  variants='turn mix50 rank50'
fi
for variant in $variants; do
  "$HOME/chess-tk/.venv/bin/python" frontier_probe.py --variant "$variant" --cpu "$cpu"
done
