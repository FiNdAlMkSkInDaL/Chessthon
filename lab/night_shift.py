#!/usr/bin/env python3
"""14-hour signer night shift. Measurement only — no training, no book, no promote.

This is the classical-engine use of a 2-core box: one-variable bricks, then KEEP/KILL.
Self-play does not update weights. Morning human reads MORNING_REPORT.txt.

Order (highest expected Elo/hour first):
  1. Restage improving from last-good; only screen if NUMBA_READY.
  2. bp-numba (bishop pair in pesto_nb).
  3. rfp60 then ff150 (single-constant screens).
  4. Contest-TC flag soak of the submitted last-good zip.
Never copies dist/last-good.zip.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/botuser/chess-tk")
VENV = ROOT / ".venv" / "bin" / "python"
CAND = Path("/home/botuser/chess-candidates")
DIST = ROOT / "dist"
LOG = ROOT / "lab" / "logs"
REPORT = LOG / "MORNING_REPORT.txt"
LAST_GOOD = DIST / "last-good"

FAST_GAMES_SCREEN = 120
BP_SCREEN_GAMES = 200
SOAK_GAMES = 40
TC_GAMES = 8


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append(line: str) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def run(
    args: list[str],
    *,
    cwd: Path = ROOT,
    env: dict | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    e = os.environ.copy()
    if env:
        e.update(env)
    print(f"$ {' '.join(args)}", flush=True)
    return subprocess.run(args, cwd=cwd, env=e, check=False, timeout=timeout)


def py(args: list[str], **kw) -> subprocess.CompletedProcess:
    return run([str(VENV), *args], **kw)


def jsonl_stats(path: Path) -> str:
    if not path.is_file():
        return f"{path.name}: missing"
    wins = draws = losses = fails = n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        n += 1
        if row.get("our_fail"):
            fails += 1
        we = row.get("we")
        result = row.get("result")
        if result == "draw":
            draws += 1
        elif result in {"white", "black"} and we in {"white", "black"}:
            if (result == "white") == (we == "white"):
                wins += 1
            else:
                losses += 1
    scored = wins + draws + losses
    score = (wins + draws / 2) / scored if scored else 0.0
    return (
        f"{path.name}: games={n} +{wins} ={draws} -{losses} "
        f"score={score:.1%} fails={fails}"
    )


def warmup(tree: Path) -> tuple[bool, str]:
    if not (tree / "agent.py").is_file():
        return False, f"{tree}: missing agent.py"
    r = subprocess.run(
        [
            str(VENV),
            "-c",
            "import core_nb; ok=bool(core_nb.warmup()); "
            "print(f'NUMBA_READY={core_nb.NUMBA_READY} WARMUP_S={core_nb.WARMUP_S:.2f} ok={ok}')",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(tree)},
        capture_output=True,
        text=True,
        timeout=70,
        check=False,
    )
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()[-400:]
    line = f"{tree.name} exit={r.returncode} {out}"
    if err:
        line += f" err={err}"
    ready = r.returncode == 0 and "NUMBA_READY=True" in out
    return ready, line


def pack(tree: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = py(
        ["-m", "harness.package", "--out", str(dest)],
        cwd=tree,
        env={**os.environ, "PYTHONPATH": f"{tree}:{ROOT}"},
    )
    append(f"pack {dest.name} exit={r.returncode}")


def gauntlet(
    agent: Path,
    opponent: str,
    games: int,
    log: Path,
    *,
    base_ms: int = 3000,
    increment_ms: int = 50,
) -> int:
    r = py(
        [
            "-m",
            "lab.gauntlet",
            "--agent",
            str(agent),
            "--opponent",
            opponent,
            "--games",
            str(games),
            "--base-ms",
            str(base_ms),
            "--increment-ms",
            str(increment_ms),
            "--log",
            str(log),
        ]
    )
    append(jsonl_stats(log))
    append(f"gauntlet exit={r.returncode} log={log.name}")
    return r.returncode


def soak_then_screen(name: str, tree: Path, *, screen_games: int) -> None:
    append(f"=== {utc()} {name} soak {SOAK_GAMES} vs greedy ===")
    soak_log = LOG / f"night-{name}-soak.jsonl"
    rc = gauntlet(tree, "baselines/greedy", SOAK_GAMES, soak_log)
    if rc != 0:
        append(f"{name}: soak failed — skip screen, do not pack")
        return
    pack(tree, DIST / f"{name}.zip")
    append(f"=== {utc()} {name} screen {screen_games} vs path last-good ===")
    screen_log = LOG / f"night-{name}-screen.jsonl"
    gauntlet(tree, str(LAST_GOOD), screen_games, screen_log)
    py(["-m", "lab.screen", str(screen_log), "--min-games", str(min(120, screen_games))])


def diagnose_and_improving() -> None:
    append(f"=== {utc()} diagnose / restage improving ===")
    ready_old, line_old = warmup(CAND / "improving")
    append(f"existing improving: {line_old}")
    r = py(
        [
            str(ROOT / "lab" / "stage_improving.py"),
            str(CAND / "improving"),
            "--src",
            str(LAST_GOOD),
        ]
    )
    if r.returncode != 0:
        append("improving restage FAILED — skip")
        return
    ready, line = warmup(CAND / "improving")
    append(f"restaged improving: {line}")
    if not ready:
        append("improving NUMBA_READY is False — skip soak/screen (would be Python vs Numba)")
        return
    if ready_old and not ready:
        append("warmup regressed after restage")
    soak_then_screen("improving", CAND / "improving", screen_games=FAST_GAMES_SCREEN)


def bp_numba() -> None:
    append(f"=== {utc()} stage bp-numba ===")
    r = py(
        [
            str(ROOT / "lab" / "stage_bp_numba.py"),
            str(CAND / "bp-numba"),
            "--src",
            str(LAST_GOOD),
        ]
    )
    if r.returncode != 0:
        append("bp-numba stage FAILED")
        return
    env = {**os.environ, "PYTHONPATH": f"{CAND / 'bp-numba'}:{ROOT}"}
    t = py(["-m", "lab.test_c"], env=env)
    append(f"test_c exit={t.returncode}")
    if t.returncode != 0:
        append("bp-numba test_c FAILED — skip gauntlet")
        return
    ready, line = warmup(CAND / "bp-numba")
    append(line)
    if not ready:
        append("bp-numba NUMBA_READY False — skip")
        return
    soak_then_screen("bp-numba", CAND / "bp-numba", screen_games=BP_SCREEN_GAMES)


def const_brick(name: str, old: str, new: str) -> None:
    append(f"=== {utc()} stage {name} ===")
    dst = CAND / name
    r = py(
        [
            str(ROOT / "lab" / "stage_const.py"),
            str(dst),
            "--src",
            str(LAST_GOOD),
            "--old",
            old,
            "--new",
            new,
        ]
    )
    if r.returncode != 0:
        append(f"{name} stage FAILED")
        return
    ready, line = warmup(dst)
    append(line)
    if not ready:
        append(f"{name} NUMBA_READY False — skip")
        return
    soak_then_screen(name, dst, screen_games=FAST_GAMES_SCREEN)


def contest_tc_soak(log_name: str = "night-real-tc.jsonl") -> None:
    append(f"=== {utc()} contest-TC soak last-good vs greedy ({TC_GAMES} games) ===")
    gauntlet(
        LAST_GOOD,
        "baselines/greedy",
        TC_GAMES,
        LOG / log_name,
        base_ms=120_000,
        increment_ms=500,
    )


def summarize() -> None:
    append(f"=== {utc()} summary ===")
    for name in (
        "night-improving-soak.jsonl",
        "night-improving-screen.jsonl",
        "night-bp-numba-soak.jsonl",
        "night-bp-numba-screen.jsonl",
        "night-rfp60-soak.jsonl",
        "night-rfp60-screen.jsonl",
        "night-ff150-soak.jsonl",
        "night-ff150-screen.jsonl",
        "night-real-tc.jsonl",
        "night-real-tc2.jsonl",
        "night-rfp100-soak.jsonl",
        "night-rfp100-screen.jsonl",
        "night-checkext64-soak.jsonl",
        "night-checkext64-screen.jsonl",
        "night-asp16-soak.jsonl",
        "night-asp16-screen.jsonl",
        "improving-screen.jsonl",
        "clock-floor-clean.jsonl",
    ):
        path = LOG / name
        if path.is_file():
            append(jsonl_stats(path))
            py(["-m", "lab.screen", str(path), "--min-games", "1"])
    append("DO NOT PROMOTE OVERNIGHT. Human reads this file after 14:00.")
    append("Submitted zip remains dist/last-good.zip (SEE + clock-floor).")
    append("Promote a candidate only if soak fails=0 AND screen KEEP (or HOLD+0-fail for floor-like).")
    append("A FEN->UCI trap book was not built. Contest openings are unpublished; hit-rate ~0.")


DEADLINE = datetime(2026, 9, 4, 13, 0, tzinfo=timezone.utc)


def past_deadline() -> bool:
    return datetime.now(timezone.utc) >= DEADLINE


def tail() -> None:
    """Fill leftover hours until 13:00Z / 14:00 BST. Does not touch last-good.zip."""
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    started = time.monotonic()
    append(f"=== night tail start {utc()} ===")
    jobs = (
        ("rfp100", lambda: const_brick("rfp100", "RFP_MARGIN = 80", "RFP_MARGIN = 100")),
        ("checkext64", lambda: const_brick("checkext64", "CHECK_EXT_PLY = 48", "CHECK_EXT_PLY = 64")),
        ("asp16", lambda: const_brick("asp16", "ASPIRATION = 25", "ASPIRATION = 16")),
        ("tc2", lambda: contest_tc_soak("night-real-tc2.jsonl")),
    )
    for name, job in jobs:
        if past_deadline():
            append(f"deadline 13:00Z reached — skip {name} and later")
            break
        job()
    summarize()
    hours = (time.monotonic() - started) / 3600.0
    append(f"=== night tail end {utc()} wall={hours:.2f}h ===")


def main() -> None:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    started = time.monotonic()
    skip_improving = "--skip-improving" in sys.argv
    append(f"=== night shift start {utc()} ===")
    append("VPS job = gated measurement, not learning. No Texel, no net, no Polyglot.")
    if skip_improving:
        append(
            "SKIP improving screen: restage warmup was NUMBA_READY=True ~21s. "
            "Prior 9% vs last-good was not a JIT miss. Brick stays dead."
        )
    else:
        diagnose_and_improving()
    bp_numba()
    const_brick("rfp60", "RFP_MARGIN = 80", "RFP_MARGIN = 60")
    const_brick("ff150", "FF_MARGIN = 200", "FF_MARGIN = 150")
    contest_tc_soak()
    summarize()
    hours = (time.monotonic() - started) / 3600.0
    append(f"=== night shift end {utc()} wall={hours:.2f}h ===")


if __name__ == "__main__":
    if "--tail" in sys.argv:
        tail()
    else:
        main()
