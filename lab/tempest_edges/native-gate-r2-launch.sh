#!/bin/bash
set -euo pipefail
cd "$HOME/chess-sign-odin-20260905/tempest-edges-native-r1"
# Module execution places the validation workspace on Python's import path.
"$HOME/chess-tk/.venv/bin/python" -B -m lab.odin.release.native_gate --validation-root "$PWD" --harness-root "$PWD/lab/tempest_build/official-284724ab" --archive "$PWD/native/tables_guard/candidate-linux-x86.zip" --cpu 0 --cold-target 55 --odin-rules --output "$PWD/native/tables_guard/native-gate-r2.json"
