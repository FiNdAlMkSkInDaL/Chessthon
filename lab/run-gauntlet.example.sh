#!/bin/sh
# Example only. Run on the Linux x86_64 HOST after collectors are paused.
# Two agent processes + the official referee. Not inside the 2g signer container
# (that envelope is one agent: cold init, nps, pack). Do not put hostnames here.
#
#   python3.12 -m lab.openings --regen          # once
#   python3.12 -m lab.gauntlet --seed-last-good # once, if dist/last-good.zip missing
#   python3.12 -m lab.gauntlet --hours 8 --opponent baselines/greedy \
#       --log lab/logs/gauntlet.jsonl
#
# Self-play SPRT (still measurement, not training):
#   python3.12 -m lab.gauntlet --hours 8 --opponent last-good --sprt \
#       --log lab/logs/sprt.jsonl
#
# This does not update PeSTO. Copy last-good yourself after flag-rate 0.
set -e
cd "$(dirname "$0")/.."
mkdir -p lab/logs dist
python3.12 -m lab.gauntlet --hours 8 --opponent baselines/greedy --log lab/logs/gauntlet.jsonl
