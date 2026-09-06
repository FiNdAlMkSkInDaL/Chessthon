#!/bin/bash
# Wait for the main night shift, then fill until 14:00 BST. Do not start a second gauntlet in parallel.
set -eu
cd /home/botuser/chess-tk
while pgrep -f '[.]venv/bin/python /home/botuser/chess-tk/lab/night_shift.py --skip-improving' >/dev/null 2>&1; do
  sleep 30
done
exec /home/botuser/chess-tk/.venv/bin/python /home/botuser/chess-tk/lab/night_shift.py --tail
