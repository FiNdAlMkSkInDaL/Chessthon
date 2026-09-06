#!/bin/sh
set -eu
cd "$HOME/chess-sign-odin-20260905/agamemnon-decision"
cpu="$1"
if [ "$cpu" = 0 ]; then
    variants='mixed25 pair-deep25 pair25 replay25 static-deep25 static25'
else
    variants='mixed50 pair-deep50 pair50 replay50 static-deep50 static50'
fi
for variant in $variants; do
    "$HOME/chess-tk/.venv/bin/python" probe.py --variant "$variant" --cpu "$cpu"
done
