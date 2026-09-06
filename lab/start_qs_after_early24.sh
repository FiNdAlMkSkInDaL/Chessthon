#!/bin/bash
# Wait for the early24 python process (not the leftover tmux argv), then screen qs-checks.
set -euo pipefail
cd /home/botuser/chess-tk
mkdir -p lab/logs
while pgrep -f '^/home/botuser/chess-tk/.venv/bin/python /home/botuser/chess-tk/lab/run_early24_tc.py' >/dev/null 2>&1; do
  echo "waiting_early24 $(date -u +%H:%M:%S)"
  sleep 15
done
echo "starting_qs $(date -u +%FT%TZ)"
exec /home/botuser/chess-tk/.venv/bin/python /home/botuser/chess-tk/lab/run_qs_checks.py
