#!/bin/sh
# Run only after the selected CPU's holdout lane and all its agents have exited.
# This script never repacks ZIPs or edits the tested engine files.
set -eu
BENCH_STAGE=$(realpath "${1:?existing absolute signer stage required}")
BENCH_CPU=${2:-1}
case "$BENCH_STAGE" in "$HOME"/chess-sign-storm-*) ;; *) exit 64 ;; esac
case "$BENCH_CPU" in 0|1) ;; *) exit 64 ;; esac
BENCH_PY=${SIGNER_PYTHON:-"$HOME/chess-tk/.venv/bin/python"}
BENCH_OUTPUT="$BENCH_STAGE/native-efficiency-r2-v3.json"
test ! -e "$BENCH_OUTPUT" || { echo 'Refusing to overwrite existing efficiency evidence' >&2; exit 64; }
cd "$BENCH_STAGE"
systemd-run --user --quiet --wait --pipe --collect --unit="storm-efficiency-$$" \
    -p MemoryMax=2147483648 -p MemorySwapMax=0 -p CPUQuota=100% \
    -p TasksMax=128 -p RuntimeMaxSec=220 -p RestrictAddressFamilies=AF_UNIX \
    -p NoNewPrivileges=yes /usr/bin/taskset -c "$BENCH_CPU" /usr/bin/env \
    PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
    BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONPATH="$BENCH_STAGE" \
    "$BENCH_PY" -m lab.storm.native_efficiency \
    --r2 "$BENCH_STAGE/storm-v4-linux-x86.zip" \
    --v3 "$BENCH_STAGE/agent-v3-linux-x86.zip" \
    --cpu "$BENCH_CPU" --output "$BENCH_OUTPUT"
