#!/bin/sh
set -eu
while systemctl --user is-active --quiet agamemnon-blends-0.service; do sleep 5; done
cd "$HOME/chess-sign-odin-20260905/agamemnon-confirm-replay25"
exec "$HOME/chess-tk/.venv/bin/python" -B -m lab.odin.release.native_gate \
    --validation-root "$PWD" --harness-root "$PWD/lab/tempest_build/official-284724ab" \
    --archive candidate-linux-x86.zip --cpu 0 --cold-target 80 --odin-rules --output native-gate.json
