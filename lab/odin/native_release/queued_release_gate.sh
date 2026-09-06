#!/bin/bash
set -euo pipefail
stage="$1"
cpu="$2"
previous="$3"
cd "$stage"
while systemctl --user is-active --quiet "$previous"; do sleep 5; done
py="$HOME/chess-tk/.venv/bin/python"
"$py" -m lab.odin.release.native_gate --validation-root "$stage" --harness-root "$stage/lab/odin/official-harness-91f70e54" --archive "$stage/candidate-linux-x86.zip" --cpu "$cpu" --cold-target 60 --odin-rules --output "$stage/native-gate.json"
for phase in supplemental state; do
    if [[ "$phase" == supplemental ]]; then
        command=("$py" "$stage/lab/odin/storm_plus/verify.py" --source "$stage/source" --output "$stage/supplemental.json" --native --cpu "$cpu")
    else
        command=("$py" "$stage/lab/odin/native_release/rule_differential.py" --source "$stage/source" --diagnostics "$stage/lab/odin/odin-diagnostics.jsonl" --output "$stage/state-gate.json" --cycle-heuristic --total-fifty --cpu "$cpu")
    fi
    systemd-run --user --quiet --wait --pipe --collect --unit="chesstk-odin-r10-$phase" -p MemoryMax=2147483648 -p MemorySwapMax=0 -p CPUQuota=100% -p TasksMax=128 -p RuntimeMaxSec=240 -p RestrictAddressFamilies=AF_UNIX -p NoNewPrivileges=yes /usr/bin/taskset -c "$cpu" /usr/bin/env PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 "${command[@]}"
done
echo 'RELEASE_VALIDATION_COMPLETE; strength plan not started by this job.'
