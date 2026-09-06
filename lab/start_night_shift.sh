#!/bin/bash
# Signer-only: stop the dead improving screen and start the night shift.
set -euo pipefail
cd /home/botuser/chess-tk
mkdir -p lab/logs

# Dead / leftover jobs — do not touch sshd or fail2ban.
pkill -f 'lab.gauntlet --agent /home/botuser/chess-candidates/improving' || true
pkill -f 'harness/runner.py /home/botuser/chess-candidates/improving' || true
pkill -f 'harness/runner.py /home/botuser/chess-tk/dist/last-good' || true
pkill -f 'clock-bisect-floor.jsonl' || true
pkill -f 'clock-floor-screen-w1' || true
sleep 2

if pgrep -af 'lab.gauntlet' | grep -v night_shift >/dev/null 2>&1; then
  echo "WARN: a gauntlet is still running:"
  pgrep -af 'lab.gauntlet' || true
fi

tmux kill-session -t night 2>/dev/null || true
tmux new-session -d -s night '/home/botuser/chess-tk/.venv/bin/python /home/botuser/chess-tk/lab/night_shift.py --skip-improving 2>&1 | tee -a /home/botuser/chess-tk/lab/logs/night_shift.out'
sleep 2
tmux ls
echo '--- night_shift.out tail ---'
tail -n 20 lab/logs/night_shift.out || true
echo '--- pgrep ---'
pgrep -af 'night_shift|lab.gauntlet' || true
