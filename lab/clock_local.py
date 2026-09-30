"""Laptop clock-cap bakeoff. Flags and think-time only — ARM Elo is a liar.

Does not promote, does not pack a freeze zip, does not restage dynamic ID.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "dist" / "clock_candidates"
LOG = ROOT / "lab" / "logs"
SUMMARY = LOG / "clock-local-summary.json"

# Curated-style ply from the rated PGNs (FEN fullmove 7 ≈ 12–13 half-moves).
START_PLY = 13
INC_MS = 500
START_MS = 120_000

# Round 1 / 2 first-move FENs (black to move). White probe uses a sibling opening.
R1_FEN = "rnbq1rk1/ppp2ppp/5n2/3p4/1b1P4/2NBP3/PP2NPPP/R1BQK2R b KQ - 1 7"
R2_FEN = "r2qkb1r/pp2pppp/2n2n2/3p4/3P1Bb1/1QPB4/PP3PPP/RN2K1NR b KQkq - 4 7"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def py(args: list[str], *, env: dict | None = None, timeout: float | None = None) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    if env:
        e.update(env)
    print("$", " ".join(args), flush=True)
    return subprocess.run(args, cwd=ROOT, env=e, check=False, timeout=timeout)


def load_alloc(tree: Path):
    # Drop prior candidate so the next time_nb wins.
    sys.path[:] = [p for p in sys.path if "clock_candidates" not in p.replace("\\", "/")]
    sys.path.insert(0, str(tree))
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    for name in list(sys.modules):
        if name == "time_nb" or name.startswith("time_nb."):
            del sys.modules[name]
    import time_nb  # noqa: PLC0415

    return time_nb.allocation


def simulate(
    allocation,
    *,
    our_moves: int,
    start_ply: int = START_PLY,
    start_ms: int = START_MS,
    inc_ms: int = INC_MS,
    spend_frac: float = 0.95,
    overrun_every: int = 0,
) -> dict:
    time_left = float(start_ms)
    ply = start_ply
    panicked = 0
    flagged_at = None
    min_left = time_left
    spends: list[float] = []
    for i in range(our_moves):
        mode, soft, hard = allocation(int(time_left), ply)
        if mode == "panic":
            panicked += 1
            spent = 80.0
        elif overrun_every and (i + 1) % overrun_every == 0:
            spent = hard
        else:
            spent = min(hard, max(1.0, soft * spend_frac))
        spends.append(spent)
        if spent > time_left:
            flagged_at = i + 1
            time_left = time_left - spent
            break
        time_left = time_left - spent + inc_ms
        min_left = min(min_left, time_left)
        ply += 2
    return {
        "moves": our_moves,
        "flagged_at": flagged_at,
        "final_ms": round(time_left, 1),
        "min_ms": round(min_left, 1),
        "panicked": panicked,
        "mean_spend_ms": round(sum(spends) / len(spends), 1) if spends else 0.0,
        "first_soft_ms": round(allocation(start_ms, start_ply)[1], 1),
        "first_hard_ms": round(allocation(start_ms, start_ply)[2], 1),
    }


def bank_table(names: list[str]) -> dict[str, dict]:
    rows = {}
    for name in names:
        allocation = load_alloc(CAND / name)
        rows[name] = {
            "open_120s": {
                "soft_ms": round(allocation(120_000, 13)[1], 1),
                "hard_ms": round(allocation(120_000, 13)[2], 1),
            },
            "r1_35_fair": simulate(allocation, our_moves=35),
            "r2_66_fair": simulate(allocation, our_moves=66),
            "r2_66_overrun8": simulate(allocation, our_moves=66, overrun_every=8),
            "late_30s_ply80": {
                "soft_ms": round(allocation(30_000, 80)[1], 1),
                "hard_ms": round(allocation(30_000, 80)[2], 1),
            },
        }
    return rows


def soak(name: str, games: int, base_ms: int, increment_ms: int) -> dict:
    log = LOG / f"clock-cap-{name}-soak.jsonl"
    if log.exists():
        log.unlink()
    agent = CAND / name
    r = py(
        [
            sys.executable,
            "-m",
            "lab.gauntlet",
            "--agent",
            str(agent),
            "--opponent",
            "baselines/greedy",
            "--games",
            str(games),
            "--base-ms",
            str(base_ms),
            "--increment-ms",
            str(increment_ms),
            "--log",
            str(log),
        ],
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(agent), str(ROOT)))},
    )
    fails = 0
    n = 0
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            n += 1
            if row.get("our_fail"):
                fails += 1
    return {"exit": r.returncode, "games": n, "fails": fails, "log": str(log)}


def probe(name: str, fen: str, time_left_ms: int) -> dict:
    agent = CAND / name
    code = (
        "import time, agent, core_nb\n"
        f"fen = {fen!r}\n"
        "print('NUMBA_READY', getattr(core_nb, 'NUMBA_READY', None))\n"
        "t0 = time.perf_counter()\n"
        f"uci = agent.get_move(fen, {int(time_left_ms)})\n"
        "ms = (time.perf_counter() - t0) * 1000.0\n"
        "print(uci)\n"
        "print(round(ms, 1))\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(agent),
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(agent), str(ROOT)))},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    ready = None
    for ln in lines:
        if ln.startswith("NUMBA_READY"):
            ready = ln.split()[-1]
    uci = None
    think = None
    if len(lines) >= 2:
        uci = lines[-2]
        try:
            think = float(lines[-1])
        except ValueError:
            think = None
    return {
        "exit": r.returncode,
        "uci": uci,
        "think_ms": think,
        "numba_ready": ready,
        "stderr_tail": (r.stderr or "")[-400:],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Laptop remaining_our cap bakeoff.")
    parser.add_argument("--banks-only", action="store_true")
    parser.add_argument("--skip-soak", action="store_true")
    parser.add_argument("--skip-probe", action="store_true")
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--base-ms", type=int, default=6000)
    parser.add_argument("--increment-ms", type=int, default=50)
    args = parser.parse_args()

    os.chdir(ROOT)
    LOG.mkdir(parents=True, exist_ok=True)
    from lab.stage_clock_cap import VARIANTS, stage_all

    print(f"=== clock local {utc()} ===", flush=True)
    stage_all(CAND)
    names = list(VARIANTS)
    banks = bank_table(names)
    print(json.dumps({"banks": banks}, indent=2), flush=True)
    soaks = {}
    probes = {}
    if args.skip_soak and SUMMARY.is_file():
        soaks = json.loads(SUMMARY.read_text(encoding="utf-8")).get("soaks") or {}
    if not args.banks_only:
        for name in names:
            if not args.skip_soak:
                print(f"=== soak {name} ===", flush=True)
                soaks[name] = soak(
                    name,
                    games=args.games,
                    base_ms=args.base_ms,
                    increment_ms=args.increment_ms,
                )
                print(soaks[name], flush=True)
            if not args.skip_probe:
                print(f"=== probe {name} R1 120s ===", flush=True)
                probes[name] = {"r1_120s": probe(name, R1_FEN, 120_000)}
                print(probes[name], flush=True)
    summary = {
        "ts": utc(),
        "note": "Laptop ARM/3.14. Elo is a liar. Use flags + think_ms vs first_soft_ms.",
        "parent": "the signer archive (not in git) / last-good (SEE+clock-floor), remaining_our cap only.",
        "banks": banks,
        "soaks": soaks,
        "probes": probes,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"wrote {SUMMARY}", flush=True)


if __name__ == "__main__":
    main()
