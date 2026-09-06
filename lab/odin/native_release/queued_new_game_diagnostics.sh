#!/bin/bash
set -euo pipefail
stage="$1"
while systemctl --user is-active --quiet chesstk-odin-final-r10-a.service; do sleep 5; done
py="$HOME/chess-tk/.venv/bin/python"
cd "$stage"
systemd-run --user --quiet --wait --pipe --collect --unit=chesstk-odin-new-game-native-probes -p MemoryMax=2147483648 -p MemorySwapMax=0 -p CPUQuota=100% -p TasksMax=128 -p RuntimeMaxSec=600 -p RestrictAddressFamilies=AF_UNIX -p NoNewPrivileges=yes /usr/bin/taskset -c 0 /usr/bin/env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 "$py" -B -u "$stage/lab/odin/new_games/probe_odin.py" --cpu 0 --source "$stage/source" --roots "$stage/lab/odin/new_games/native-diagnostic-roots.json" --output "$stage/new-games-native-probes.jsonl"
