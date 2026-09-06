"""Measurement loop: mixed FENs, flag-rate, optional SPRT vs last-good.

This does not train PeSTO, does not write weights, and does not upload.
Promote last-good yourself after flag-rate 0 — never from this process.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from harness.referee import FAILED_TERMINATIONS, play_match
from harness.rules import PLY_CAP
from harness.sandbox import local
from lab.openings import FENS, opening_fen

FAST_BASE_MS = 10_000
FAST_INCREMENT_MS = 100
LAST_GOOD_NAME = "last-good.zip"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_agent(spec: str, root: Path) -> Path:
    if spec in {"last-good", "last_good"}:
        packed = root / "dist" / LAST_GOOD_NAME
        unpacked = root / "dist" / "last-good"
        if (unpacked / "agent.py").is_file():
            return unpacked
        if packed.is_file():
            unpacked.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(packed) as archive:
                archive.extractall(unpacked)
            if not (unpacked / "agent.py").is_file():
                raise SystemExit(f"{packed} has no agent.py at zip root")
            return unpacked
        raise SystemExit(
            f"no {packed} (or {unpacked}/agent.py). "
            "Pack one with: python -m harness.package --out dist/last-good.zip"
        )
    path = Path(spec)
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    if path.is_file() and path.suffix.lower() == ".zip":
        dest = path.with_suffix("")
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(dest)
        path = dest
    if not (path / "agent.py").is_file():
        raise SystemExit(f"{path} has no agent.py")
    return path


def we_failed(plays_white: bool, result: str, termination: str) -> bool:
    if termination not in FAILED_TERMINATIONS:
        return False
    if termination == "both_failed":
        return True
    we_lost = (result == "black") if plays_white else (result == "white")
    return we_lost


def opponent_failed(plays_white: bool, result: str, termination: str) -> bool:
    if termination not in FAILED_TERMINATIONS or termination == "both_failed":
        return False
    return not we_failed(plays_white, result, termination)


def candidate_score(plays_white: bool, result: str) -> float | None:
    if result == "draw":
        return 0.5
    if result == "void":
        return None
    won_white = result == "white"
    return 1.0 if won_white == plays_white else 0.0


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


def sprt_llr(
    wins: int,
    draws: int,
    losses: int,
    *,
    elo0: float,
    elo1: float,
) -> float:
    n = wins + draws + losses
    if n == 0:
        return 0.0
    draw_ratio = draws / n
    p0 = trinomial(elo0, draw_ratio)
    p1 = trinomial(elo1, draw_ratio)
    counts = (losses, draws, wins)
    llr = 0.0
    for count, a, b in zip(counts, p0, p1, strict=True):
        if count:
            llr += count * math.log(max(b, 1e-12) / max(a, 1e-12))
    return llr


def sprt_bounds(alpha: float, beta: float) -> tuple[float, float]:
    return math.log(beta / (1.0 - alpha)), math.log((1.0 - beta) / alpha)


def sprt_verdict(llr: float, lower: float, upper: float) -> str:
    if llr >= upper:
        return "H1"
    if llr <= lower:
        return "H0"
    return "continue"


def pair_index(score_a: float, score_b: float) -> int:
    return int(round((score_a + score_b) * 2.0))


def append_jsonl(path: Path | None, row: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def _seed_last_good(root: Path) -> Path:
    dest = root / "dist" / LAST_GOOD_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        print(f"already have {dest}")
        return dest
    from harness.package import build

    written = build(root, dest, ("weights",))
    print(f"seeded {dest} with {', '.join(written)}")
    return dest


def run(arguments: argparse.Namespace) -> int:
    root = _repo_root()
    if arguments.seed_last_good:
        _seed_last_good(root)
        if arguments.games == 0 and arguments.hours <= 0:
            return 0

    agent = resolve_agent(arguments.agent, root)
    opponent = resolve_agent(arguments.opponent, root)
    if agent.resolve() == opponent.resolve():
        raise SystemExit("agent and opponent are the same directory; copy last-good first")

    log_path = Path(arguments.log) if arguments.log else None
    if log_path is not None and not log_path.is_absolute():
        log_path = (root / log_path).resolve()

    use_openings = not arguments.startpos
    if use_openings and len(FENS) < 2:
        raise SystemExit("openings.fen missing; run python -m lab.openings --regen")

    wins = draws = losses = 0
    our_fails = Counter()
    their_fails = Counter()
    terminations: Counter[str] = Counter()
    pentanomial = [0, 0, 0, 0, 0]
    pair_first: float | None = None
    started = time.monotonic()
    deadline = started + arguments.hours * 3600.0 if arguments.hours > 0 else None
    lower, upper = sprt_bounds(arguments.alpha, arguments.beta)
    played = 0
    target = arguments.games if arguments.games > 0 else 10**9

    print(
        f"gauntlet {agent} vs {opponent}  "
        f"base={arguments.base_ms}ms+{arguments.increment_ms}  "
        f"{'openings' if use_openings else 'startpos'}  "
        f"{'SPRT' if arguments.sprt else 'no-SPRT'}",
        flush=True,
    )

    try:
        while played < target:
            if deadline is not None and time.monotonic() >= deadline:
                print("hour budget reached", flush=True)
                break
            game_no = played + arguments.game_offset
            plays_white = game_no % 2 == 0
            fen = chess_startpos() if not use_openings else opening_fen(game_no // 2)
            white, black = (agent, opponent) if plays_white else (opponent, agent)
            game_started = time.monotonic()
            outcome = play_match(
                local(white),
                local(black),
                arguments.base_ms,
                arguments.increment_ms,
                ply_cap=arguments.ply_cap,
                start_fen=fen,
            )
            elapsed = time.monotonic() - game_started
            played += 1
            terminations[outcome.termination] += 1
            ours = we_failed(plays_white, outcome.result, outcome.termination)
            theirs = opponent_failed(plays_white, outcome.result, outcome.termination)
            if ours:
                our_fails[outcome.termination] += 1
            if theirs:
                their_fails[outcome.termination] += 1
            points = candidate_score(plays_white, outcome.result)
            if points == 1.0:
                wins += 1
            elif points == 0.5:
                draws += 1
            elif points == 0.0:
                losses += 1
            if points is not None:
                if pair_first is None:
                    pair_first = points
                else:
                    pentanomial[pair_index(pair_first, points)] += 1
                    pair_first = None
            colour = "white" if plays_white else "black"
            print(
                f"game {played}: we={colour} {outcome.result} by {outcome.termination} "
                f"({elapsed:.1f}s)",
                flush=True,
            )
            append_jsonl(
                log_path,
                {
                    "ts": _now(),
                    "game": played,
                    "we": colour,
                    "fen": fen,
                    "result": outcome.result,
                    "termination": outcome.termination,
                    "our_fail": ours,
                    "their_fail": theirs,
                    "elapsed_s": round(elapsed, 3),
                    "white": str(white),
                    "black": str(black),
                },
            )
            if ours and arguments.stop_on_fail:
                print("stopping: our agent failed a game", flush=True)
                break
            if arguments.sprt:
                llr = sprt_llr(
                    wins, draws, losses, elo0=arguments.elo0, elo1=arguments.elo1
                )
                verdict = sprt_verdict(llr, lower, upper)
                if verdict != "continue":
                    print(
                        f"SPRT {verdict}  LLR={llr:.3f}  bounds=[{lower:.3f},{upper:.3f}]",
                        flush=True,
                    )
                    break
    except KeyboardInterrupt:
        print("\ninterrupted", flush=True)

    n = played
    score = (wins + draws / 2) / n if n else 0.0
    wall = time.monotonic() - started
    print(
        f"\n{agent} vs {opponent} over {n} games in {wall / 60:.1f} min",
        flush=True,
    )
    print(f"+{wins} ={draws} -{losses}, score {score:.1%}", flush=True)
    print(
        "terminations: "
        + ", ".join(f"{name} {count}" for name, count in terminations.most_common()),
        flush=True,
    )
    print(
        "pentanomial LL LD DD WD WW: " + " ".join(str(x) for x in pentanomial),
        flush=True,
    )
    if our_fails:
        print(
            "OUR FAILS: "
            + ", ".join(f"{name} {count}" for name, count in our_fails.most_common()),
            flush=True,
        )
    else:
        print("OUR FAILS: 0", flush=True)
    if their_fails:
        print(
            "opponent fails: "
            + ", ".join(f"{name} {count}" for name, count in their_fails.most_common()),
            flush=True,
        )
    if arguments.sprt and n:
        llr = sprt_llr(wins, draws, losses, elo0=arguments.elo0, elo1=arguments.elo1)
        verdict = sprt_verdict(llr, lower, upper)
        print(
            f"SPRT {verdict} vs elo {arguments.elo0:g}/{arguments.elo1:g}  "
            f"LLR={llr:.3f}  bounds=[{lower:.3f},{upper:.3f}]",
            flush=True,
        )
        print("do not copy last-good from this process; do it yourself after flag-rate 0")
    if our_fails:
        return 1
    return 0


def chess_startpos() -> str:
    import chess

    return chess.STARTING_FEN


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Flag-rate / SPRT gauntlet. Measurement, not training."
    )
    parser.add_argument("--agent", default=".", help="directory or zip with agent.py")
    parser.add_argument(
        "--opponent",
        default="baselines/greedy",
        help="directory, zip, or 'last-good'",
    )
    parser.add_argument(
        "--games",
        type=int,
        default=None,
        help="game cap (default 20, or unlimited when --hours is set)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=0.0,
        help="stop before starting a new game after this many hours",
    )
    parser.add_argument("--base-ms", type=int, default=FAST_BASE_MS)
    parser.add_argument("--increment-ms", type=int, default=FAST_INCREMENT_MS)
    parser.add_argument("--ply-cap", type=int, default=PLY_CAP)
    parser.add_argument("--startpos", action="store_true", help="ignore openings.fen")
    parser.add_argument("--log", type=Path, help="append JSONL (e.g. lab/logs/gauntlet.jsonl)")
    parser.add_argument(
        "--game-offset",
        type=int,
        default=0,
        help="start counting at this game index (two workers, different openings)",
    )
    parser.add_argument(
        "--sprt",
        action="store_true",
        help="stop at H0/H1 (use vs last-good, not vs greedy)",
    )
    parser.add_argument("--elo0", type=float, default=0.0)
    parser.add_argument("--elo1", type=float, default=10.0)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--beta", type=float, default=0.05)
    parser.add_argument(
        "--stop-on-fail",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="halt on our crash/flag/illegal/init (default on)",
    )
    parser.add_argument(
        "--seed-last-good",
        action="store_true",
        help="if dist/last-good.zip is missing, pack the current tree into it",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="2 games, 2s+50ms, ply 30 vs random — proves the loop, not Elo",
    )
    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    if arguments.quick:
        arguments.games = 2
        arguments.hours = 0.0
        arguments.base_ms = 2000
        arguments.increment_ms = 50
        arguments.ply_cap = 30
        arguments.opponent = "baselines/random"
        arguments.sprt = False
        if arguments.log is None:
            arguments.log = Path("lab/logs/gauntlet-quick.jsonl")
    elif arguments.games is None:
        arguments.games = 0 if arguments.hours > 0 else 20
    if arguments.opponent in {"last-good", "last_good"} and not arguments.sprt:
        arguments.sprt = True
    raise SystemExit(run(arguments))


if __name__ == "__main__":
    main()
