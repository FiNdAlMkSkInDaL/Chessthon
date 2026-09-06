#!/usr/bin/env python3
from pathlib import Path
p = Path("/home/botuser/chess-tk/lab/logs/promotions.jsonl")
p.parent.mkdir(parents=True, exist_ok=True)
row = (
    '{"ts":"2026-09-03T21:36:00Z","brick":"clock-floor","parent":"see-main",'
    '"gates":["soak-40-0-fail","screen-120-0-fail-HOLD-49pct","seq-2x120s-checkmate"],'
    '"games":120,"score":0.492,'
    '"notes":"remaining_our floor 1; 3s Elo noise; smoke both colours checkmate"}\n'
)
p.write_text(p.read_text(encoding="utf-8") + row if p.exists() else row, encoding="utf-8")
print("logged clock-floor")
