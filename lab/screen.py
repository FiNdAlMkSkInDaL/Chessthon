"""Merge parallel gauntlet JSONL logs and apply a 4-hour screening rule.

Not SPRT H1/H0 — fast keep/kill/hold for time-boxed decisions.
Usage:
  python -m lab.screen lab/logs/see-sprt.jsonl lab/logs/see-w2.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def expected_score(elo: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-elo / 400.0))


def trinomial(elo: float, draw_ratio: float) -> tuple[float, float, float]:
    score = expected_score(elo)
    draw = min(max(draw_ratio, 1e-6), 1.0 - 1e-6)
    draw = min(draw, 2.0 * min(score, 1.0 - score) - 1e-9)
    draw = max(draw, 1e-6)
    win = max(score - draw / 2.0, 1e-9)
    loss = max(1.0 - score - draw / 2.0, 1e-9)
    total = win + draw + loss
    return loss / total, draw / total, win / total


def sprt_llr(wins: int, draws: int, losses: int, *, elo0: float = 0.0, elo1: float = 10.0) -> float:
    n = wins + draws + losses
    if n == 0:
        return 0.0
    draw_ratio = draws / n
    p0 = trinomial(elo0, draw_ratio)
    p1 = trinomial(elo1, draw_ratio)
    llr = 0.0
    for count, a, b in zip((losses, draws, wins), p0, p1, strict=True):
        if count:
            llr += count * math.log(max(b, 1e-12) / max(a, 1e-12))
    return llr


def score_game(we: str, result: str) -> float | None:
    if result == "draw":
        return 0.5
    if result == "void":
        return None
    return 1.0 if (result == "white") == (we == "white") else 0.0


def load(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def summarize(rows: list[dict]) -> dict:
    wins = draws = losses = fails = 0
    for row in rows:
        if row.get("our_fail"):
            fails += 1
        pts = score_game(row["we"], row["result"])
        if pts == 1.0:
            wins += 1
        elif pts == 0.5:
            draws += 1
        elif pts == 0.0:
            losses += 1
    n = wins + draws + losses
    score = (wins + draws / 2) / n if n else 0.0
    return {
        "games": n,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score": score,
        "fails": fails,
        "llr": sprt_llr(wins, draws, losses),
    }


def verdict(
    stats: dict,
    *,
    min_games: int = 120,
    keep_pct: float = 0.53,
    kill_pct: float = 0.49,
) -> str:
    if stats["fails"]:
        return "KILL (our fail)"
    n = stats["games"]
    if n < min_games:
        return f"HOLD (need {min_games} games, have {n})"
    if stats["score"] >= keep_pct:
        return "KEEP (screen pass)"
    if stats["score"] <= kill_pct:
        return "KILL (screen fail)"
    return "HOLD (marginal)"


def main() -> None:
    parser = argparse.ArgumentParser(description="4-hour gauntlet screen (merge JSONL logs).")
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--min-games", type=int, default=120)
    parser.add_argument("--keep", type=float, default=0.53, help="min score to KEEP")
    parser.add_argument("--kill", type=float, default=0.49, help="max score to KILL")
    args = parser.parse_args()
    rows = load(args.logs)
    stats = summarize(rows)
    call = verdict(stats, min_games=args.min_games, keep_pct=args.keep, kill_pct=args.kill)
    print(
        f"games={stats['games']} +{stats['wins']} ={stats['draws']} -{stats['losses']} "
        f"score={stats['score']:.1%} fails={stats['fails']} LLR={stats['llr']:.3f}"
    )
    print(call)
    if call.startswith("KILL"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
