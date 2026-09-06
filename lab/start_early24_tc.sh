#!/bin/bash
# Signer-only: kill stuck night jobs, stage early24 from last-good, contest-TC soak.
# 8 games first (stop on fail). If green, 40 more at the same TC. Does not touch last-good.zip.
set -euo pipefail
cd /home/botuser/chess-tk
mkdir -p lab/logs /home/botuser/chess-candidates

# Stuck overnight waiter / leftover measurement — do not touch sshd or fail2ban.
tmux kill-session -t night 2>/dev/null || true
tmux kill-session -t night-tail 2>/dev/null || true
pkill -f 'start_night_tail.sh' || true
pkill -f '/home/botuser/chess-tk/lab/night_shift.py' || true
pkill -f 'lab.gauntlet --agent /home/botuser/chess-candidates/' || true
sleep 2

if pgrep -af 'lab.gauntlet' | grep -v early24 >/dev/null 2>&1; then
  echo "WARN: a gauntlet is still running:"
  pgrep -af 'lab.gauntlet' || true
fi

/home/botuser/chess-tk/.venv/bin/python /home/botuser/chess-tk/lab/stage_clock_cap.py \
  --parent /home/botuser/chess-tk/dist/last-good.zip \
  --out /home/botuser/chess-candidates/clock_cap \
  --only early24

TREE=/home/botuser/chess-candidates/clock_cap/early24
test -f "$TREE/agent.py"
test -f "$TREE/time_nb.py"
grep -q 'cap = 24 if game_ply < 80 else 40' "$TREE/time_nb.py"
grep -qv 'early_stop_ok' "$TREE/time_nb.py"

echo '=== warmup ==='
PYTHONPATH="$TREE:/home/botuser/chess-tk" /home/botuser/chess-tk/.venv/bin/python -c \
  "import core_nb; ok=bool(core_nb.warmup()); print(f'NUMBA_READY={core_nb.NUMBA_READY} WARMUP_S={core_nb.WARMUP_S:.2f} ok={ok}'); raise SystemExit(0 if core_nb.NUMBA_READY else 1)"

echo '=== 8-game contest-TC gate ==='
/home/botuser/chess-tk/.venv/bin/python -m lab.gauntlet \
  --agent "$TREE" \
  --opponent baselines/greedy \
  --games 8 \
  --base-ms 120000 \
  --increment-ms 500 \
  --stop-on-fail \
  --log /home/botuser/chess-tk/lab/logs/early24-tc8.jsonl
echo "GATE_EXIT=$?"

echo '=== 40-game contest-TC soak ==='
/home/botuser/chess-tk/.venv/bin/python -m lab.gauntlet \
  --agent "$TREE" \
  --opponent baselines/greedy \
  --games 40 \
  --base-ms 120000 \
  --increment-ms 500 \
  --stop-on-fail \
  --log /home/botuser/chess-tk/lab/logs/early24-tc40.jsonl
echo "SOAK_EXIT=$?"
echo 'DO NOT PROMOTE. Human reads the jsonl.'
